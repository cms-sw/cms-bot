WORKSPACE=$(pwd)

blacklist_path="$HOME/workspace/cache/blacklist"
nodes_path="$HOME/nodes/"
email_notification="cms-sdt-logs@cern.ch"
job_url="${JENKINS_URL}job/nodes-sanity-check/${BUILD_NUMBER}"
echo $PATHS >> $WORKSPACE/paths.param
echo $SINGULARITY >> $WORKSPACE/paths.param

function run_check {
    node=$1
    SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
    scp $SSH_OPTS ${WORKSPACE}/cms-bot/jenkins/nodes-sanity-check.sh ${WORKSPACE}/paths.param "cmsbuild@$node:/tmp" || (echo "Cannot scp script" && exit 1)
    ssh $SSH_OPTS "cmsbuild@"$node 'sh /tmp/nodes-sanity-check.sh'; exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        rm -f "$blacklist_path/$node"
    else
        echo "... ERROR! Blacklisting ${node} ..."
	# Check if node is already in the blacklist
	if [ ! -e $blacklist_path/$node ]; then 
            touch "$blacklist_path/$node"
            notify_failure $email_notification $node $job_url
            # If aarch or ppc, disconnect node
	    node_regex="$(echo $node | cut -d "-" -f 1)*$(echo $node | cut -d "-" -f 2)*"
	    for match in $(find $nodes_path -name $node_regex); do
	        jenkins_node=$(echo $match | rev | cut -d "/" -f 1 | rev)
                node_off $jenkins_node
            done
	else
            echo "Node already in blacklist. Skipping notification ..."
        fi
    fi
}

function lxplus_cleanup {
    lxplus_hosts=$@
    blacklist_content="$HOME/workspace/cache/blacklist/*"

    for file in $blacklist_content; do
        filename="${file##*/}"
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
    ${JENKINS_CLI_CMD} offline-node ${affected_node} -m "Node\ ${affected_node}\ has\ been\ blacklisted"
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
