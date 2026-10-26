#!/bin/bash -e
s3bucket="s3://cmsrep"
s3cmd="$1"
if [ ! -x "${s3cmd}" ] ; then
  echo "ERROR: No such file: $s3cmd"
  exit 1
fi
days_to_keep="$2"
[ "$2" == "" ] && days_to_keep=60
threshold=$(date -d "$days_to_keep days ago" '+%Y-%m-%d')
del=0
MAX_JOBS=8

$s3cmd ls -r ${s3bucket}/.meta_data/store/ > keep_files.txt
for arch in $($s3cmd ls ${s3bucket}/store/ | grep '^\s\s*DIR\s' | sed "s|.*${s3bucket}/store/||;s|/*$||" | sort) ; do
  echo "Working on $arch"
  $s3cmd ls ${s3bucket}/store/${arch}/ | sort > files.txt
  adel=0
  kept=0
  while read -r date time size url; do
    AGE="Unknown"
    DEL_IT=false
    rpm=$(echo ${url}| sed 's|.*/||')
    if grep -q "/${rpm}" keep_files.txt ; then
      AGE="MetaData"
    elif [[ "$date" > "$threshold" ]] ; then
      for json in $(find /data/cmssw/repos/cms/${arch} -mindepth 2 -maxdepth 2 -name RPMS.json) ; do
        if [ $(grep "${rpm}" $json |wc -l) -gt 0 ] ; then
          AGE="REPO"
          DEL_IT=true
          break
        fi
      done
    else
      AGE="$date"
      DEL_IT=true
    fi
    if $DEL_IT ; then
      while [ $(jobs -p | wc -l) -ge ${MAX_JOBS} ]; do sleep 0.2 ; done
      echo "$rpm ($AGE)"
      $s3cmd rm ${s3bucket}/store/${arch}/${rpm} &
      let del=$del+1
      let adel=$adel+1
    else
      let kept=$kept+1
    fi
  done < files.txt
  echo "Architecture $arch: ${kept}/${adel} active/deleted"
done
wait
echo "Deleted $del files"
