blacklist_content="/build/workspace/cache/blacklist/*"
nodes_path="/build/nodes/*"
job_url="${JENKINS_URL}job/nodes-sanity-check"
node_base_url="${JENKINS_URL}computer"

#email_address="cms-sdt-logs@cern.ch"
email_address="andrea.valenzuela.ramirez@cern.ch"

function notify {
    MSG=$1
    SBJ=$2
    EMAIL=$3

    echo $MSG
    echo "$MSG" | mail -s "$SBJ" $EMAIL
}

# Summary of offline nodes
for d in $nodes_path/config.xml; do
  if [[ -n $(grep "\$UserCause\|\$ByCLI" $d) ]]; then
    node=$(echo $d | awk '{split($0,a,"/"); print a[4]}')
    node_url=$(echo "$node_base_url/$node/")
    offline_reason=$(grep -e "string" -m 2 $d | awk '{split($0,a,"<string>|</string>"); print a[2]}' | tail -n 1)
    offline_person=$(grep -e "string" -m 1 $d | awk '{split($0,a,"<string>|</string>"); print a[2]}')
    msg=$(echo -e "Node $node has been manually marked as offline by $offline_person because of $offline_reason.\n\nPlease check if it should be already online:\n$node_url")
    sbj=$(echo "[REMINDER] Node $node is still offline")
    notify "$msg" "$sbj" $email_address
  fi
done


# Summary of blacklisted nodes
for file in $blacklist_content; do
    nodes_list=()
    filename=$(basename $file)
    offline_file=$(echo $filename | grep ".offline" | wc -l)
    if [ $offline_file -gt 0 ]; then continue; fi
    if [[ "$filename" == "*" ]]; then continue; fi
    sbj=$(echo "[REMINDER] Node $filename is still blacklisted")
    node_url=$(echo "$node_base_url/$filename/")
    for folder in $nodes_path; do
        node=$(grep agentCommand $folder/config.xml | tr ' <>' '\n\n\n' | grep '@' | sort | uniq | cut -d "@" -f 2 | cut -d "." -f 1)
        if [[ $node == $filename ]]; then
            nodes_list+="$node_base_url/$(basename $folder)\n"
        fi
    done
    msg=$(echo -e "Host $filename has been blacklisted by job $job_url.\n\nPlease check if it should be already online at the corresponding Jenkins nodes:\n$nodes_list")
    notify "$msg" "$sbj" $email_address
done
