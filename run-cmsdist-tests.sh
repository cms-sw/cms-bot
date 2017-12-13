#!/bin/sh -ex
CMS_BOT_DIR=$(dirname $0)
case $CMS_BOT_DIR in /*) ;; *) CMS_BOT_DIR=$(pwd)/${CMS_BOT_DIR} ;; esac
if [ "X$CMSDIST_PR" == X ]; then
  echo "Error: CMSDIST_PR variable must be set"
  exit 0
fi

function Jenkins_GetCPU ()
{
  ACTUAL_CPU=$(getconf _NPROCESSORS_ONLN)
  case $(hostname) in lxplus* ) let ACTUAL_CPU=$ACTUAL_CPU/2 ;; esac
  if [ "$ACTUAL_CPU" = "0" ] ; then ACTUAL_CPU=1; fi
  if [ "X$1" != "X" ] ; then let ACTUAL_CPU=$ACTUAL_CPU$1 ; fi
  echo $ACTUAL_CPU
}

set +x
JENKINS_PREFIX=$(echo "${JENKINS_URL}" | sed 's|/*$||;s|.*/||')
if [ "X${JENKINS_PREFIX}" = "X" ] ; then JENKINS_PREFIX="jenkins"; fi
if [ "X${PUB_USER}" = X ] ; then export PUB_USER="cms-sw" ; fi
PUB_REPO="${PUB_USER}/cmsdist"
if [ "X$PULL_REQUEST" != X ]; then PUB_REPO="${PUB_USER}/cmssw" ; fi
CMS_WEEKLY_REPO=cms.week$(echo $(tail -1 $CMS_BOT_DIR/ib-weeks | sed 's|.*-||') % 2 | bc)
GH_COMMITS=$(curl -s https://api.github.com/repos/${PUB_USER}/cmsdist/pulls/$CMSDIST_PR/commits)
GH_JSON=$(curl -s https://api.github.com/repos/${PUB_USER}/cmsdist/pulls/$CMSDIST_PR)
TEST_USER=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["repo"]["owner"]["login"]')
TEST_BRANCH=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["ref"]')
CMSDIST_BRANCH=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["ref"]')
CMSDIST_COMMITS=$($CMS_BOT_DIR/process-pull-request -c -r ${PUB_USER}/cmsdist $CMSDIST_PR)
set -x
echo CMS_WEEKLY_REPO=$CMS_WEEKLY_REPO
echo TEST_USER=$TEST_USER
echo TEST_BRANCH=$TEST_BRANCH
echo CMSDIST_BRANCH=$CMSDIST_BRANCH
echo CMSDIST_COMMITS=$CMSDIST_COMMITS

if [ "X$TEST_USER" = "X" ] || [ "X$TEST_BRANCH" = "X" ]; then
  echo "Error: failed to retrieve user or branch to test."
  exit 0
fi

ARCH_MATCH="SCRAM_ARCH="
if [ "X$ARCHITECTURE" != X ]; then
  ARCH_MATCH="SCRAM_ARCH=${ARCHITECTURE};"
fi

if [ $(cat $CMS_BOT_DIR/config.map | grep -v 'NO_IB=' | grep -v 'DISABLED=1;' | grep "CMSDIST_TAG=${CMSDIST_BRANCH};" | grep "${ARCH_MATCH}" | wc -l) -gt 1 ] ; then
  CONFIG_LINE=$(cat $CMS_BOT_DIR/config.map | grep -v 'NO_IB='| grep -v 'DISABLED=1;' | grep "CMSDIST_TAG=${CMSDIST_BRANCH};" | grep "${ARCH_MATCH}" | grep "PR_TESTS=1")
else
  CONFIG_LINE=$(cat $CMS_BOT_DIR/config.map | grep -v 'NO_IB='| grep -v 'DISABLED=1;' | grep "CMSDIST_TAG=${CMSDIST_BRANCH};" | grep "${ARCH_MATCH}")
fi

if [ "X$CMSSW_CYCLE" = X ]; then
  CMSSW_CYCLE=$(echo "$CONFIG_LINE" | tr ';' '\n' | grep RELEASE_QUEUE= | sed 's|RELEASE_QUEUE=||')
fi

if [ "X$PKGTOOLS_BRANCH" = X ]; then
  PKGTOOLS_BRANCH=$(echo "$CONFIG_LINE" | tr ';' '\n' | grep PKGTOOLS_TAG= | sed 's|PKGTOOLS_TAG=||')
fi

if [ "X$ARCHITECTURE" = X ]; then
  ARCHITECTURE=$(echo "$CONFIG_LINE" | tr ';' '\n' | grep SCRAM_ARCH= | sed 's|SCRAM_ARCH=||')
fi

if [ "X$ARCHITECTURE" = X ]; then
  echo "Unable to find the ARCHITECTURE for $CMSDIST_BRANCH"
  exit 1
fi
export ARCHITECTURE

REAL_ARCH=-`cat /proc/cpuinfo | grep vendor_id | head -n 1 | sed "s/.*: //"`
CMSSW_IB=
for relpath in $(scram -a $ARCHITECTURE l -c $CMSSW_CYCLE | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests"  | awk '{print $2":"$3}' | sort -r | sed 's|^.*:||') ; do
  [ -e $relpath/build-errors ] && continue
  CMSSW_IB=$(basename $relpath)
  break
done
[ "X$CMSSW_IB" = "X" ] && CMSSW_IB=$(scram -a $ARCHITECTURE l -c $CMSSW_CYCLE | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests" | awk '{print $2}' | tail -n 1)

BUILD_DIR="testBuildDir"

$CMS_BOT_DIR/modify_comment.py -r ${PUB_USER}/cmsdist -t JENKINS_TEST_URL -m "https://cmssdt.cern.ch/${JENKINS_PREFIX}/job/${JOB_NAME}/${BUILD_NUMBER}/console" $CMSDIST_PR || true
# If a CMSSW PR is also being tested update the comment on its page too
if [ "X$PULL_REQUEST" != X ]; then
  $CMS_BOT_DIR/modify_comment.py -r ${PUB_USER}/cmssw -t JENKINS_TEST_URL -m "https://cmssdt.cern.ch/${JENKINS_PREFIX}/job/${JOB_NAME}/${BUILD_NUMBER}/console" $PULL_REQUEST || true
fi
git clone git@github.com:${PUB_USER}/cmsdist $WORKSPACE/CMSDIST -b $CMSDIST_BRANCH
git clone git@github.com:cms-sw/pkgtools $WORKSPACE/PKGTOOLS -b $PKGTOOLS_BRANCH

cd $WORKSPACE/CMSDIST
git pull git://github.com/$TEST_USER/cmsdist.git $TEST_BRANCH
# Check which packages the PR changes
PKGS=
for c in $CMSDIST_COMMITS ; do
  for p in $(git show --pretty='format:' --name-only $c | grep '.spec$' | grep -v 'cmssw-toolfile' | grep -v 'cmssw-patch' | sed 's|.spec$|-toolfile|') ; do
    [ -f $WORKSPACE/CMSDIST/$p.spec ] || continue
    PKGS="$PKGS $p"
  done
done
PKGS=$(echo $PKGS |  tr ' ' '\n' | sort | uniq)

export CMSDIST_COMMIT=$(echo $CMSDIST_COMMITS | sed 's|.* ||')
cd $WORKSPACE

# Notify github that the script will start testing now
$CMS_BOT_DIR/report-pull-request-results TESTS_RUNNING --repo $PUB_USER/cmsdist --pr $CMSDIST_PR -c $CMSDIST_COMMIT --pr-job-id ${BUILD_NUMBER} $DRY_RUN

if [ $(grep "CMSDIST_TAG=$CMSDIST_BRANCH;" $CMS_BOT_DIR/config.map | grep "RELEASE_QUEUE=$CMSSW_CYCLE;" | grep "SCRAM_ARCH=$ARCHITECTURE;" | grep ";ENABLE_DEBUG=" | wc -l) -eq 0 ] ; then
  DEBUG_SUBPACKS=$(grep '^ *DEBUG_SUBPACKS=' $CMS_BOT_DIR/build-cmssw-ib-with-patch | sed 's|.*DEBUG_SUBPACKS="||;s|".*$||')
  pushd $WORKSPACE/CMSDIST
    perl -p -i -e 's/^[\s]*%define[\s]+subpackageDebug[\s]+./#subpackage debug disabled/' $DEBUG_SUBPACKS
  popd
fi

# Build the whole cmssw-tool-conf toolchain
COMPILATION_CMD="PKGTOOLS/cmsBuild --builders 3 -i $WORKSPACE/$BUILD_DIR --repository $CMS_WEEKLY_REPO  --arch $ARCHITECTURE -j $(Jenkins_GetCPU) build $PKGS cmssw-tool-conf"
echo $COMPILATION_CMD > $WORKSPACE/cmsswtoolconf.log
(eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
echo 'END OF BUILD LOG'
echo '--------------------------------------'

RESULTS_FILE=$WORKSPACE/testsResults.txt
touch $RESULTS_FILE

TEST_ERRORS=$(grep -E "Error [0-9]$" $WORKSPACE/cmsswtoolconf.log) || true
GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/cmsswtoolconf.log) || true

if [ "X$TEST_ERRORS" != X ] || [ "X$GENERAL_ERRORS" == X ]; then
  $CMS_BOT_DIR/report-pull-request-results PARSE_BUILD_FAIL --report-pr $CMSDIST_PR --repo ${PUB_USER}/cmsdist --pr $CMSDIST_PR -c $CMSDIST_COMMIT --pr-job-id ${BUILD_NUMBER} --unit-tests-file $WORKSPACE/cmsswtoolconf.log
  if [ "X$PULL_REQUEST" != X ]; then
    $CMS_BOT_DIR/report-pull-request-results PARSE_BUILD_FAIL --report-pr $CMSDIST_PR  --repo ${PUB_USER}/cmssw --pr $PULL_REQUEST --pr-job-id ${BUILD_NUMBER} --unit-tests-file $WORKSPACE/cmsswtoolconf.log
  fi
  echo 'PR_NUMBER;'$CMSDIST_PR >> $RESULTS_FILE
  echo 'ADDITIONAL_PRS;'$ADDITIONAL_PULL_REQUESTS >> $RESULTS_FILE
  echo 'BASE_IB;'$CMSSW_IB >> $RESULTS_FILE
  echo 'BUILD_NUMBER;'$BUILD_NUMBER >> $RESULTS_FILE
  echo 'CMSSWTOOLCONF_RESULTS;ERROR' >> $RESULTS_FILE
  # creation of results summary file, normally done in run-pr-tests, here just to let close the process
  cp $CMS_BOT_DIR/templates/PullRequestSummary.html $WORKSPACE/summary.html
  sed -e "s|@JENKINS_PREFIX@|$JENKINS_PREFIX|g;s|@REPOSITORY@|$PUB_REPO|g" $CMS_BOT_DIR/templates/js/renderPRTests.js > $WORKSPACE/renderPRTests.js
  exit 0
else
  echo 'CMSSWTOOLCONF_RESULTS;OK' >> $RESULTS_FILE
fi

# Create an appropriate CMSSW area
export SCRAM_ARCH=$ARCHITECTURE
scram -a $SCRAM_ARCH project $CMSSW_IB
echo /cvmfs/cms.cern.ch > $WORKSPACE/$BUILD_DIR/etc/scramrc/links.db
source $WORKSPACE/$BUILD_DIR/cmsset_default.sh

if [ $(grep '^V05-05-' $CMSSW_IB/config/config_tag | wc -l) -gt 0 ] ; then
  if [ $(sed -e 's|^V05-05-||' $CMSSW_IB/config/config_tag) -lt 74 ] ; then
    git clone git@github.com:cms-sw/cmssw-config
    pushd cmssw-config
      git checkout master
    popd
    mv $CMSSW_IB/config/SCRAM $CMSSW_IB/config/SCRAM.orig
    cp -r cmssw-config/SCRAM $CMSSW_IB/config/SCRAM
  fi
fi
cd $CMSSW_IB/src

# Setup all the toolfiles previously built
SET_ALL_TOOLS=NO
if [ $(echo $CMSSW_IB | grep '^CMSSW_9' | wc -l) -gt 0 ] ; then SET_ALL_TOOLS=YES ; fi
set +x
DEP_NAMES=
CTOOLS=../config/toolbox/${ARCHITECTURE}/tools/selected
for xml in $(ls $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/cms/cmssw-tool-conf/*/tools/selected/*.xml) ; do
  name=$(basename $xml)
  tool=$(echo $name | sed 's|.xml$||')
  echo "Checking tool $tool ($xml)"
  if [ $tool = "cmsswdata" ] ; then
    CHG=0
    for dd in $(grep 'CMSSW_DATA_PACKAGE=' $xml | sed 's|.*="||;s|".*||') ; do
      if [ $(grep "=\"$dd\"" $CTOOLS/$name | wc -l) -eq 1 ] ; then continue ; fi
      CHG=1
      break
    done
    if [ X$CHG = X0 ] ; then
      if [ "$SET_ALL_TOOLS" = "YES" ] ; then cp -f $xml $CTOOLS/$name ; fi
      continue 
    fi
  elif [ -e $CTOOLS/$name ] ; then
    nver=$(grep '<tool ' $xml          | tr ' ' '\n' | grep 'version=' | sed 's|version="||;s|".*||g')
    over=$(grep '<tool ' $CTOOLS/$name | tr ' ' '\n' | grep 'version=' | sed 's|version="||;s|".*||g')
    echo "Checking version in release: $over vs $nver"
    if [ "$nver" = "$over" ] ; then
      if [ "${SET_ALL_TOOLS}" = "YES" ] ; then cp -f $xml $CTOOLS/$name ; fi
      continue
    fi
    echo "Settings up $name: $over vs $nver" 
  fi
  cp -f $xml $CTOOLS/$name
  DEP_NAMES="$DEP_NAMES echo_${tool}_USED_BY"
  echo "Setting up new tool: $tool"
  scram setup $tool
done
if [ "${SET_ALL_TOOLS}" = "YES" ] ; then 
  scram setup
else
  #Move away gcc directory
  mv $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/external/gcc $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/external/gcc-move-away
fi
scram build -r 
eval $(scram runtime -sh)
set -x
echo $PYTHONPATH | tr ':' '\n'

# Search for CMSSW package that might depend on the compiled externals
touch $WORKSPACE/cmsswtoolconf.log
if [ "X${DEP_NAMES}" != "X" ] ; then
  CMSSW_DEP=$(scram build ${DEP_NAMES} | tr ' ' '\n' | grep '^cmssw/\|^self/' | cut -d"/" -f 2,3 | sort | uniq)
  if [ "X${CMSSW_DEP}" != "X" ] ; then
    git cms-addpkg $CMSSW_DEP 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
  fi
fi
# Launch the standard ru-pr-tests to check CMSSW side passing on the global variables
$CMS_BOT_DIR/run-pr-tests
