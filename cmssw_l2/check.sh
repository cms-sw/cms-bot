#!/bin/bash -e
push_chg=true
if [ "$1" = "" -o "$1" = "false" ] ; then push_chg=false ; fi
sdir=$(dirname $0)
[ -f ${sdir}/l2.json ] || echo '{}' > ${sdir}/l2.json
old_commit=""
[ -f ${sdir}/commit.txt ] && old_commit=$(cat ${sdir}/commit.txt)..

rm -rf update_cmssw_l2
git clone -q git@github.com:cms-sw/cms-bot update_cmssw_l2
pushd update_cmssw_l2
  export PYTHONPATH=$(/bin/pwd -P)
  export PYTHONUNBUFFERED=1
  commit=""
  for data in $(git log --no-merges --pretty=format:"%H:%at," ${old_commit} -- categories.py | tr ',' '\n' | grep : | tac) ; do
    commit=$(echo $data | sed 's|:.*||')
    cur_time=$(echo $data | sed 's|.*:||')
    git checkout -q $commit
    rm -rf *.pyc __pycache__
    echo "Working on $commit"
    ${sdir}/update.py ${sdir}/l2.json ${cur_time} 2>&1
  done
popd
rm -rf update_cmssw_l2
if [ "${commit}" != "" ] ; then
  pushd ${sdir}
    echo "${commit}" > commit.txt
    if $push_chg ; then
      git add commit.txt l2.json
      git commit -a -m "Updated CMSSW L2 category information."
      if ! git push origin ; then
        git pull --rebase
        git push origin
      fi
    fi
  popd
fi
