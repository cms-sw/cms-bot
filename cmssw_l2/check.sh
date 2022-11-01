#!/bin/bash -ex
push_chg=true
default_commit_limits=50
if [ "$1" = "" -o "$1" = "false" ] ; then push_chg=false ; fi
sdir=$(realpath $(dirname $0))
[ -f ${sdir}/l2.json ] || echo '{}' > ${sdir}/l2.json
old_commit="$(tail -1 ${sdir}/commit.txt)"
new_commit="${old_commit}"
commit_cnt=0
rm -rf update_cmssw_l2
git clone -q git@github.com:cms-sw/cms-bot update_cmssw_l2
pushd update_cmssw_l2
  export PYTHONPATH=$(/bin/pwd -P)
  export PYTHONUNBUFFERED=1
  git checkout ${old_commit}
  for data in $(git log --no-merges --pretty=format:"%H:%at," ${old_commit}..master | tr ',' '\n' | grep : | tac) ; do
    commit=$(echo $data | sed 's|:.*||')
    cur_time=$(echo $data | sed 's|.*:||')
    let commit_cnt=${commit_cnt}+1
    git cherry-pick --allow-empty $commit
    if [ $(git diff --name-only HEAD^ | grep "^categories.py" | wc -l) -gt 0 ] ; then
      [ $(grep $commit ${sdir}/commit.txt | wc -l) -eq 0 ] || continue
      new_commit="${commit}"
      commit_cnt=0
      echo "Working on $commit"
      ${sdir}/update.py ${sdir}/l2.json ${cur_time} 2>&1
      rm -rf *.pyc __pycache__
    fi
  done
  if [ ${commit_cnt} -gt ${default_commit_limits} ] ; then
    new_commit="${commit}"
  fi
popd
rm -rf update_cmssw_l2
if [ "${new_commit}" != "${old_commit}" ] ; then
  echo ${commit} >> ${sdir}/commit.txt
  pushd ${sdir}
    if $push_chg ; then
      git add commit.txt l2.json
      git commit -a -m "Updated CMSSW L2 category information ${new_commit}"
      if ! git push origin ; then
        git pull --rebase
        git push origin
      fi
    fi
  popd
fi
