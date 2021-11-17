#!/bin/bash -ex
sdir=$(dirname $0)
[ -f ${sdir}/all_l2.json ] || echo '{}' > ${sdir}/all_l2.json
old_commit=""
[ -f ${sdir}/last_commit.txt ] && old_commit=$(cat ${sdir}/last_commit.txt)..

rm -rf update_cmssw_l2
git clone git@github.com:cms-sw/cms-bot update_cmssw_l2

pushd update_cmssw_l2
  export PYTHONPATH=$(/bin/pwd -P)
  commit=""
  for data in $(git log --no-merges --pretty=format:"%H:%at" ${old_commit} -- categories.py | tac) ; do
    commit=$(echo $data | sed 's|:.*||')
    cut_time=$(echo $data | sed 's|.*:||')
    git checkout -q $commit
    ${sdir}/update.py ${sdir}/all_l2.json ${cut_time}
  done
popd
rm -rf update_cmssw_l2
if [ ${commit} != "" ] ; then
  pushd ${sdir}
    echo "${commit}" > last_commit.txt
    git add last_commit.txt all_l2.json
    git commit -a -m "Updated CMSSW L2 category information."
  popd
fi
