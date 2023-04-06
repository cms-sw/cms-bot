WORKSPACE=$(pwd)

blacklist_path="$HOME/workspace/cache/blacklist"
if [ ! -d $blacklist_path ]; then
    mkdir -p $blacklist_path
fi

if [[ "$TEST_SINGLE_LXPLUS_HOST" == "true" ]]; then
    # Check that is actually a lxplusWXYZ node
    for node in ${NODES[@]}; do
        echo $node | grep -E "lxplus[0-9]{2}"; exit_code=$?
        if [ $exit_code -gt 0 ]; then echo "Host ${node} is not a valid lxplusXYZ host. Please, set TEST_SINGLE_LXPLUS_HOST to false or indicate a valid host." && exit 1; fi
    done
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
        # Special .offline cleanup for aarch and ppc nodes
        if [[ $(echo $node | grep -e 'olarm\|ibmminsky' | wc -l) -gt 0 ]]; then
            aarch_ppc_cleanup $node
        fi
    else
        echo "... ERROR! Blacklisting ${node} ..."
	# Check if node is already in the blacklist
	if [ ! -e $blacklist_path/$node ]; then 
            touch "$blacklist_path/$node" || exit 1
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

function get_jenkins_nodenames {
    node=$1
    nodes_content_path="$HOME/nodes/*"
    jenkins_nodes_list=()
    for folder in $nodes_content_path; do
        jenkins_node=$(grep agentCommand $folder/config.xml | tr ' <>' '\n\n\n' | grep '@' | sort | uniq | cut -d "@" -f 2 | cut -d "." -f 1)
        if [[ $jenkins_node == $node ]]; then
            jenkins_nodes_list+="$(basename $folder) "
        fi
    done
}

function lxplus_disconnect {
    nodes_list="$HOME/logs/slaves/lxplus*"
    host=$1
    node_off_list=()
    for lxplus_node in $nodes_list; do
        if [ -e $lxplus_node/slave.log ]; then
            match=$(cat $lxplus_node/slave.log | grep -a "ssh -q" | grep $host)
            lxplus_node=$(basename $lxplus_node)
            if [ "X$match" != "X" ]; then
                echo "Node $lxplus_node is connected to host $host ... Marking $lxplus_node as offline, if needed ..."
                node_off_list+="$lxplus_node "
                node_off $lxplus_node
            else
                echo "Node $lxplus_node not connected to $host. Skipping ..."
            fi
        fi
    done
    if [[ "X$node_off_list" != "X" ]]; then
        notify_failure $email_notification $host $job_url $node_off_list
    fi

}

function aarch_ppc_disconnect {
    nodes_path="$HOME/nodes/*"
    host=$1
    node_off_list=()   
    for folder in $nodes_path; do
        node=$(grep agentCommand $folder/config.xml | tr ' <>' '\n\n\n' | grep '@' | sort | uniq | cut -d "@" -f 2 | cut -d "." -f 1)
        if [[ $node == $host ]]; then
            agent=$(basename $folder)
            echo "Marking node $agent as offline ..."
            node_off_list+="$agent "
            node_off $agent
        fi
    done
    if [[ "X$node_off_list" != "X" ]]; then
        notify_failure $email_notification $host $job_url $node_off_list
    fi
}

function notify_failure {
    email=$1; shift
    node=$1; shift
    job_url=$1; shift
    node_off_list=$@
    job_description="This job runs a sanity check for /afs, /cvmfs repositories and singularity."
    node_info="Jenkins nodes ${node_off_list[@]} have been marked offline since they where connected to host ${node}."
    error_msg="Node ${node} has been blacklisted by ${job_url}/console. Please, take the appropiate action. ${node_info} ${job_description}"
    echo $error_msg | mail -s "Node ${node} has been blacklisted" $email
}

function node_off {
    affected_node=$1
    ${JENKINS_CLI_CMD} offline-node ${affected_node} -m "Node\ ${affected_node}\ has\ been\ blacklisted"
    # Store that node has been set offline
    echo "Storing .offline info at: $blacklist_path"
    touch "$blacklist_path/$affected_node.offline"
}

function node_on {
    affected_node=$1
    ${JENKINS_CLI_CMD} online-node ${affected_node}
    # Remove offline flag
    echo "Removing .offline info at: $blacklist_path"
    rm -rf "$blacklist_path/$affected_node.offline"
}

function connect_node {
    affected_node=$1
    ${JENKINS_CLI_CMD} connect-node ${affected_node}
    # Remove offline flag
    echo "Removing .offline info at: $blacklist_path"
    rm -rf "$blacklist_path/$affected_node.offline"
}

function lxplus_blacklist_cleanup {
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

function lxplus_offline_cleanup {
    offline_content="$HOME/workspace/cache/blacklist/lxplus*.offline"

    for file in $offline_content; do
        filename=$(basename $file)
        node_name=$(echo $filename | cut -d "." -f 1)
        if [[ "$node_name" == "*" ]]; then
            echo "No offline nodes found ... Skipping cleanup!"
            break
        fi
        echo "Offline file found for $node_name ... Cleannig up, if needed."
        node_info=$(curl -H "OIDC_CLAIM_CERN_UPN: cmssdt" "${LOCAL_JENKINS_URL}/computer/$node_name/api/json?pretty=true")
        node_tempoffline=$(echo $node_info | grep '"temporarilyOffline" : true' | wc -l)
        if [ $node_tempoffline -eq 0 ]; then $(rm -rf $file) && continue; fi # External action has been taken
        node_idle=$(echo $node_info | grep '"idle" : true' | wc -l)
        if [ $node_idle -gt 0 ]; then
            echo "Bringing node $node_name online again ..."
            node_on $node_name  # Brings node online, but it stays connected to the buggy host
            connect_node $node_name  # We need to send the connect command so that the jenkins node is re-connected
        fi
    done
}

function aarch_ppc_cleanup {
    node=$1
    get_jenkins_nodenames $node

    echo ${jenkins_nodes_list[@]}
    for node_name in ${jenkins_nodes_list[@]}; do
        if [ -e "$blacklist_path/$node_name.offline" ]; then
            offline_reason=$(grep -e "string" -m 2 "$nodes_path/$node_name/config.xml" | awk '{split($0,a,"<string>|</string>"); print a[2]}' | tail -n 1)
            if [ $(echo $offline_reason | grep "has been blacklisted" | wc -l) -gt 0 ]; then
                echo "Bringing node $node_name online again ..."
                node_on $node_name
            fi
        fi
    done
}

# Main
lxplus_hosts=()

for node in ${NODES[@]}; do
    echo "Processing $node ..."
    if ([[ "$node" =~ .*"lxplus".* ]] && [[ "$TEST_SINGLE_LXPLUS_HOST" == "false" ]]); then
        echo "Searching for lxplus hosts ..."
        for ip in $(host $node | grep 'has address' | sed 's|^.* ||'); do
            real_nodename=$(host $ip | grep 'domain name' | sed 's|^.* ||;s|\.$||')
            lxplus_hosts+="$real_nodename "
            echo "[$real_nodename]"
            run_check $real_nodename
        done
    else
        if [[ "$TEST_SINGLE_LXPLUS_HOST" == "true" ]]; then
            if [ $(echo $node | grep ".cern.ch" | wc -l) -eq 0 ]; then
                node="${node}.cern.ch"
            fi
            lxplus_hosts+=$node
        fi
        run_check $node
    fi
done


# Cleanup of lxplus hosts, if needed
if [ $(echo "${NODES[@]}" | grep "lxplus" | wc -l) -gt 0 ]; then
    if [[ "$TEST_SINGLE_LXPLUS_HOST" == "false" ]]; then 
        lxplus_blacklist_cleanup $lxplus_hosts
    fi
    lxplus_offline_cleanup
fi
