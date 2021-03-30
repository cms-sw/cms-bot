#!/bin/bash -e
$base=$1
[ "${base}" != "" ] || exit 1
[ -d "${base}" ] || exit 1
items=$(ls -l $base | grep '^d' | grep ' zh ' | awk '{print $3":"$9}' | sort ) 
for user in $(echo $items | tr ' ' '\n' | sed 's|:.*||' | uniq) ; do
  dirs=$(echo $items | tr ' ' '\n' | grep "^${user}:" | sed "s|.*:|${base}/|")
  size=$(du -csm $dirs | tail -1 | sed 's|\s.*||')
  echo "$user ${size}MB ${dirs}"
done
