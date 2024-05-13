#!/bin/bash
this_dir=$(dirname $0)
source ${this_dir}/os.sh
for d in $(echo $1 | tr '/' ' ' | grep -v '^$'); do
  this_dir="${this_dir}/${d}"
  if [ -e ${this_dir}.sh ] ; then
    source ${this_dir}.sh
    echo "${this_dir}.sh"
  fi
done
