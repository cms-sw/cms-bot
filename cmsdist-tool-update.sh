#!/bin/bash -ex

# This script will update CMSSW external, whose version we keep patched
# It expects that git username is setuped locally
# Parameters:
# $1 - CMSDIST branch (ex: IB/CMSSW_10_5_X/rootnext)
# $2 - external(tool) name, (ex: root, dd4hep)
# $3 - Optional: external branch from where we want to take changes (ex: master)
#      Default value is obtained from cmsdist/<tool>.spec using '%define branch <prefix>/<branch>/<commit>'
#
#
# During execution, script will ask if to cherry-pick specific commits
# After execution it creates 'push-branches.sh' and 'tool' directory
# You can check 'tool' if merge was successful and then execute 'push-branches.sh'
# This will push the changes as separate branches. Then you will need to make a PR.
#
############################################################
function get_rpm_marco_value (){
  #Needs spec file path and rpm variable
  grep "^ *%define  *$2 " $1 | tail -1 | sed "s|.*$2  *||;s| *$||"
}
function get_package_info (){
  #Needs the spec file path in $1
  #Returns cmsrepo:branch:commit:fork_repo
  gh_user=$(get_rpm_marco_value $1 github_user)
  for line in $(grep '^Source' ${1} | grep 'github.com' | sed 's|.*github.com/||;s| .*$||') ; do
     local cmsrep=$(echo $line      | sed "s|\?.*$||;s|\.git$||;s|\%||;s|{||;s|}||;s|github_user|${gh_user}|")
     local objinfo=$(echo $line     | sed 's|.*obj=||;s|&.*$||')
     local branch=$(echo ${objinfo} | sed 's|/.*$||;s|\%||;s|{||;s|}||')
     local commit=$(echo ${objinfo} | sed 's|^.*/||;s|\%||;s|{||;s|}||')
     local fork_repo=$(curl -s https://api.github.com/repos/${cmsrep} | grep forks_url | tail -1 | sed 's|.*/api.github.com/repos/||;s|/forks.*||')
     echo "${cmsrep}:${branch}:${commit}:${fork_repo}"
  done
}
function commit_cmsdist(){
  local TOOL=$1
  local TOOL_BRANCH=$2
  local PUSH_CMDS_FILE=$3
  pushd cmsdist
    git commit -a -m "Updated $TOOL to tip of branch ${TOOL_BRANCH}"
    NEW_BRANCH=$TOOL-update-${TOOL_BRANCH}-$(date +%Y%m%d)
    git checkout -b $NEW_BRANCH
    echo "cd $(/bin/pwd)" >> $PUSH_CMDS_FILE
    echo "git push my $NEW_BRANCH" >> $PUSH_CMDS_FILE
  popd
}
############################################################

CMSDIST_BRANCH=$1
TOOL=$2

if [ "X$CMSDIST_BRANCH" = "X" ] ; then echo -e "Missing cmsdist branch name\nUsage: $0 <cmsdist-branch> <tool-name> [<tool-branch>]"; exit 1; fi
if [ "X$TOOL" = "X" ] ; then echo -e "Missing tool name\nUsage: $0 <cmsdist-branch> <tool-name> [<tool-branch>]"; exit 1; fi

case $(whoami) in 
  cmsbuild|cmsbld) GITHUB_USER="cms-sw" ;;
  *) GITHUB_USER=$(cat ~/.gitconfig | grep github | sed 's|.*= *||;s| *$||') ;;
esac
if [ "X$GITHUB_USER" = "X" ] ; then
  echo "Error: Unable to find the github user name"
  exit 1
fi

if [ ! -d cmsdist ] ; then
  git clone git@github.com:cms-sw/cmsdist
  pushd cmsdist
    git remote add cms git@github.com:cms-sw/cmsdist
    git remote add my git@github.com:$GITHUB_USER/cmsdist
    git checkout $CMSDIST_BRANCH
  popd
fi

TOOL_BRANCH=$(echo $3| sed 's|:.*||')
if [ "$TOOL_BRANCH" = "" ] ; then
  TOOL_BRANCH=$(get_rpm_marco_value cmsdist/${TOOL}.spec branch |  cut -d/ -f2)
fi
if [ "X$TOOL_BRANCH" = "X" ] ; then echo "Missing tool branch name"; exit 1; fi
TOOL_CHECKOUT_CMD="; git checkout $TOOL_BRANCH"
NEW_TOOL_HASH=$(echo $3 | sed 's|.*:||')
if [ "${NEW_TOOL_HASH}" != "" ] ; then
  TOOL_CHECKOUT_CMD="${TOOL_CHECKOUT_CMD} ; git checkout ${NEW_TOOL_HASH}"
fi

PUSH_CMDS_FILE=`/bin/pwd`/push-branches.sh
COMMIT_CMSDIST=NO
if [ ! -f $PUSH_CMDS_FILE ] ; then
 COMMIT_CMSDIST=YES
 echo "#!/bin/bash -ex" > $PUSH_CMDS_FILE
 chmod +x $PUSH_CMDS_FILE
fi
if [ "X$4" = "X" ] ; then
  for line in $(get_package_info cmsdist/${TOOL}.spec) ; do
    $0 "$1" "$2" "$3" $(echo $line | tr ':' ' ')
  done
  commit_cmsdist $TOOL ${TOOL_BRANCH} $PUSH_CMDS_FILE
  exit 0
fi

TOOL_CMS_REPO=$4
TOOL_REG_BRANCH=$5
TOOL_REG_TAG=$6
TOOL_FORK_REPO=$7
TOOL_REPO_NAME=$(echo $TOOL_FORK_REPO | sed 's|.*/||')
TOOL_DOWNOAD_CMD="git clone git@github.com:${TOOL_FORK_REPO} ${TOOL_REPO_NAME}; cd ${TOOL_REPO_NAME} ${TOOL_CHECKOUT_CMD}"
OLD_CMS_BRANCH=$(get_rpm_marco_value cmsdist/${TOOL}.spec ${TOOL_REG_BRANCH})
OLD_BRANCH_PREFIX=$(echo $OLD_CMS_BRANCH | cut -d/ -f1)
OLD_TOOL_HASH=$(echo $OLD_CMS_BRANCH  | sed 's|^.*/||')
if [ "X$OLD_TOOL_HASH" = "X" ] ; then
   echo "Error: Unable to get OLD_TOOL_HASH using cmsdist/$CMSDIST_BRANCH/$TOOL.spec"
   exit 1
fi

mkdir -p tool
pushd tool
  eval $TOOL_DOWNOAD_CMD
  if [ "$NEW_TOOL_HASH" = "" ] ; then
    NEW_TOOL_HASH=$(git log --pretty=format:'%h' -n 1)
  fi
  echo "[$NEW_TOOL_HASH]"
  echo "[$OLD_TOOL_HASH]"
  if [ "$NEW_TOOL_HASH" = "$OLD_TOOL_HASH" ] ; then
    echo "New and old branches are same: $OLD_TOOL_HASH"
    exit 0
  fi
  if [ ! -d .git ] ; then
    git init
    git add .
  fi
  NEW_CMS_BRANCH=${OLD_BRANCH_PREFIX}/$TOOL_BRANCH/$NEW_TOOL_HASH
  git remote add cms git@github.com:${TOOL_CMS_REPO}
  git fetch cms $NEW_CMS_BRANCH:$NEW_CMS_BRANCH || true
  git branch
  if [ "X`git branch | grep \"^  *$NEW_CMS_BRANCH\$\"`" != "X" ] ; then
    echo "$NEW_CMS_BRANCH already exists in cms-sw/$TOOL.git"
    exit 1
  fi
  git checkout -b $NEW_CMS_BRANCH
  git fetch cms $OLD_CMS_BRANCH:$OLD_CMS_BRANCH
  echo CMS Changes
  git log --oneline $OLD_TOOL_HASH..$OLD_CMS_BRANCH | awk '{print $1}' > ../commits
  for commit in $(tac ../commits); do
    git show --oneline $commit  | head -1
    while [ true ] ; do
      echo "Cherry pick commit $commit [Y/N/Q]:"
      if [ "X$FORCE_APPLY_CMS_COMMITS" != "Xtrue" ] ; then
        read -n 1 RES
      else
        RES=Y
      fi
      if [ "X$RES" = "XY" ] ; then
        git cherry-pick $commit
        echo "Commited cherry-picked: $commit"
        break
      elif [ "X$RES" = "XN" ] ; then
        break
      elif [ "X$RES" = "XQ" ] ; then
        exit 0
      fi
    done
  done
  echo "cd $(/bin/pwd)" >> $PUSH_CMDS_FILE
  echo "git push cms $NEW_CMS_BRANCH" >> $PUSH_CMDS_FILE
  TOOL_TAG=`git log | head -1 | awk '{print $2}'`
popd

sed -i -e "s|^%define  *${TOOL_REG_BRANCH}  *${OLD_BRANCH_PREFIX}/.*$|%define ${TOOL_REG_BRANCH} $NEW_CMS_BRANCH|" cmsdist/$TOOL.spec
sed -i -e "s|^%define  *${TOOL_REG_TAG} .*$|%define ${TOOL_REG_TAG} $TOOL_TAG|" cmsdist/$TOOL.spec
if [ "$COMMIT_CMSDIST" = "YES" ] ; then
  commit_cmsdist $TOOL ${TOOL_BRANCH} $PUSH_CMDS_FILE
fi


