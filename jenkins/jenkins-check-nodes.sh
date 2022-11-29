WORKSPACE=$(pwd)

blacklist_path="$HOME/workspace/cache/blacklist"
if [ -d $blacklist_path ]; then
    mkdir -p $blacklist_path
fi

nodes_path="$HOME/nodes/"
email_notification="cms-sdt-logs@cern.ch"
job_url="${JENKINS_URL}job/nodes-sanity-check/${BUILD_NUMBER}"

function run_check {
    node=$1
    SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
    scp $SSH_OPTS ${WORKSPACE}/cms-bot/jenkins/nodes-sanity-check.sh "cmsbuild@$node:/tmp" || (echo "Cannot scp script" && exit 1)
    ssh $SSH_OPTS "cmsbuild@"$node "sh /tmp/nodes-sanity-check.sh $SINGULARITY $PATHS"; exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        rm -f "$blacklist_path/$node"
    else
        echo "... ERROR! Blacklisting ${node} ..."
	# Check if node is already in the blacklist
	if [ ! -e $blacklist_path/$node ]; then 
            touch "$blacklist_path/$node" || exit 1
            notify_failure $email_notification $node $job_url
	    if [[ $(echo $node | grep '^olarm\|^ibmminsky' | wc -l) -gt 0 ]]; then
                # If aarch or ppc, bring node off
                aarch_ppc_disconnect $node
            elif [[ $(echo $node | grep '^lxplus' | wc -l) -gt 0 ]]; then
                # If lxplus, disconnect all nodes connected to this host
                lxplus_disconnect $node
            fi
	else
            echo "Node already in blacklist. Skipping notification ..."
        fi
    fi
}

function lxplus_cleanup {
    lxplus_hosts=$@
    blacklist_content="$HOME/workspace/cache/blacklist/*"

    for file in $blacklist_content; do
	filename=$(basename $file)
        offline_file=$(echo $filename | grep ".offline" | wc -l)
        if [ $offline_file -gt 0 ]; then continue; fi
        if [[ "$filename" == "*" ]]; then
            echo "Blacklist directory empty... Skipping cleanup!"
            break
        elif [[ $(echo $filename | grep '^olarm\|^ibmminsky' | wc -l) -gt 0 ]]; then
            # No automatic cleanup for aarch and ppc nodes
            continue
        fi
        if [[ ! " ${lxplus_hosts[@]} " =~ " ${filename} " ]]; then
            echo "Affected lxplus node ${filename} is no longer a valid host. Removing it from blacklist ..."
            rm -f $file
        else
            echo "Affected lxplus node ${filename} is still a valid host. Keeping it in blacklist ..." 
        fi
    done
}

function lxplus_disconnect {
    nodes_list="$HOME/logs/slaves/lxplus*"
    host=$1
    for lxplus_node in $nodes_list; do
        if [ -e $lxplus_node/slave.log ]; then
            match=$(cat $lxplus_node/slave.log | grep -a "ssh -q" | grep $host)
            lxplus_node=$(basename $lxplus_node)
            if [ "X$match" != "X" ]; then
                echo "Node $lxplus_node is connected to host $host ... Marking $lxplus_node as offline, if needed ..."
                node_off $lxplus_node
            else
                echo "Node $lxplus_node not connected to $host. Skipping ..."
            fi
        fi
    done

}

function aarch_ppc_disconnect {
    node=$1
    node_regex="$(echo $node | cut -d "-" -f 1)*$(echo $node | cut -d "-" -f 2)*"
    for match in $(find $nodes_path -name $node_regex); do
        jenkins_node=$(echo $match | rev | cut -d "/" -f 1 | rev)
        node_off $jenkins_node
    done
}

function notify_failure {
    email=$1
    node=$2
    job_url=$3
    job_description="This job runs a sanity check for /afs, /cvmfs repositories and singularity."
    error_msg="Node ${node} has been blacklisted by ${job_url}. Please, take the appropiate action. ${job_description}"
    echo $error_msg | mail -s "Node ${node} has been blacklisted" $email
}

function node_off {
    affected_node=$1
    node_info=$(curl -H "OIDC_CLAIM_CERN_UPN: cmssdt" "http://localhost:8080/jenkins/computer/$affected_node/api/json?pretty=true")
    node_offline=$(echo $node_info | grep '"offline" : false' | wc -l)
    if [ $node_offline -gt 0 ]; then
        ${JENKINS_CLI_CMD} offline-node ${affected_node} -m "Node\ ${affected_node}\ has\ been\ blacklisted"
        # Store that node has been set offline
        echo "Storing .offline info at: $blacklist_path"
        touch "$blacklist_path/$affected_node.offline"
    fi
}

function node_on {
    affected_node=$1
    ${JENKINS_CLI_CMD} online-node ${affected_node}
    # Remove offline flag
    echo "Removing .offline info at: $blacklist_path"
    rm -rf "$blacklist_path/$affected_node.offline"
}

function offline_cleanup {
    offline_content="$HOME/workspace/cache/blacklist/*.offline"

    for file in $offline_content; do
        filename=$(basename $file)
        node_name=$(echo $filename | cut -d "." -f 1)
        if [[ "$node_name" == "*" ]]; then
            echo "No offline nodes found ... Skipping cleanup!"
            break
        fi
        echo "Offline file found for $node_name ... Cleannig up, if needed."
        node_info=$(curl -H "OIDC_CLAIM_CERN_UPN: cmssdt" "http://localhost:8080/jenkins/computer/$node_name/api/json?pretty=true")
        node_tempoffline=$(echo $node_info | grep '"temporarilyOffline" : true' | wc -l)
        if [ $node_tempoffline -eq 0 ]; then $(rm -rf $file) && continue; fi # External action has been taken
        node_offline=$(echo $node_info | grep '"offline" : true' | wc -l)
        if [ $node_offline -gt 0 ]; then
            node_idle=$(echo $node_info | grep '"idle" : true' | wc -l)
            if [ $node_idle -gt 0 ]; then
                node_on $node_name
            fi
        fi
    done
}


# Main

lxplus_hosts=()

for node in ${NODES[@]}; do
    echo "Processing $node ..."
    if [[ "$node" =~ .*"lxplus".* ]]; then
        echo "Searching for lxplus hosts ..."
        for ip in $(host $node | grep 'has address' | sed 's|^.* ||'); do
            real_nodename=$(host $ip | grep 'domain name' | sed 's|^.* ||;s|\.$||')
            lxplus_hosts+="$real_nodename "
            echo "[$real_nodename]"
            run_check $real_nodename
        done
    else
        run_check $node
    fi
done

# Cleanup of lxplus hosts
lxplus_cleanup $lxplus_hosts
offline_cleanup
