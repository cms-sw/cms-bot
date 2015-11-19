#!/bin/sh -ex

if [ "X$CMSDIST_PR" == X ]; then
  echo "Error: CMSDIST_PR variable must be set"
  exit 0
fi

function Jenkins_GetCPU ()
{
  ACTUAL_CPU=$(getconf _NPROCESSORS_ONLN)
  case $NODE_NAME in
    lxplus* ) ACTUAL_CPU=$(echo $ACTUAL_CPU / 2 | bc) ;;
  esac
  if [ "X$1" != "X" ] ; then
    ACTUAL_CPU=$(echo "$ACTUAL_CPU*$1" | bc)
  fi
  echo $ACTUAL_CPU
}
CMS_WEEKLY_REPO=cms.week`date +%g | xargs -i echo "{} % 2" | bc`
GH_JSON=$(curl -s https://api.github.com/repos/cms-sw/cmsdist/pulls/$CMSDIST_PR)
TEST_USER=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["repo"]["owner"]["login"]')
TEST_BRANCH=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["ref"]')
CMSDIST_BRANCH=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["ref"]')
CMSSW_IB=$(scram l $(echo $CMSDIST_BRANCH | cut -d"/" -f 2) | grep -v /ReleaseCandidates | tail -n 1 | awk '{print $2}')

if [ "X$TEST_USER" = "X" ] || [ "X$TEST_BRANCH" = "X" ]; then
  echo "Error: failed to retrieve user or branch to test."
  exit 0
fi

if [ "X$ARCH" == X ]; then
  ARCH=$(cat $WORKSPACE/cms-bot/config.map | grep $CMSDIST_BRANCH | grep PR_TESTS | cut -d ";" -f 1 | cut -d "=" -f 2)
fi

if [ "X$PKGTOOLS_BRANCH" == X ]; then
  PKGTOOLS_BRANCH="V00-22-XX"
fi

BUILD_DIR="testBuildDir"
export PUB_REPO="cms-sw/cmsdist"

git clone git@github.com:cms-sw/cmsdist $WORKSPACE/CMSDIST -b $CMSDIST_BRANCH
git clone git@github.com:cms-sw/pkgtools $WORKSPACE/PKGTOOLS -b $PKGTOOLS_BRANCH

cd $WORKSPACE/CMSDIST
git pull git://github.com/$TEST_USER/cmsdist.git $TEST_BRANCH
# Check which packages the PR changes
PKGS=$(git diff origin/$CMSDIST_BRANCH.. --name-only --diff-filter=ACMR | grep -v .patch | cut -d"." -f"1")

# Check if the packages have a toolfile and add them to the build if they exists
for P in $PKGS; do
  if [ -f $P-toolfile.spec ]; then
    TOOLFILES=$TOOLFILES" "$P-toolfile
  fi
  EXT_DEP=$EXT_DEP" "$(grep -nr $P . | grep "Requires:" | cut -d "/" -f 2 | cut -d ":" -f 1 | grep -v "cmssw-tool-conf" | grep -v $P | cut -d "." -f 1)
done
# Add the toolfiles of the external packages depending on the one(s) being modified
for EXT in $EXT_DEP; do
  if [ -f $EXT-toolfile.spec ]; then
    TOOLFILES=$TOOLFILES" "$EXT-toolfile
  fi
done
export CMSDIST_COMMIT=$(git log origin/$CMSDIST_BRANCH.. --pretty="%H" | tail -n 1)
cd $WORKSPACE

# Notify github that the script will start testing now
$WORKSPACE/cms-bot/report-pull-request-results TESTS_RUNNING --repo $PUB_REPO --pr $CMSDIST_PR -c $CMSDIST_COMMIT --pr-job-id ${BUILD_NUMBER} $DRY_RUN

# Build the whole cmssw-tool-conf toolchain
if [ "$FULL_TOOLCONF" = true ]; then
  COMPILATION_CMD="PKGTOOLS/cmsBuild -i $WORKSPACE/$BUILD_DIR --repository $CMS_WEEKLY_REPO  --arch $ARCH -j $(Jenkins_GetCPU) build cmssw-tool-conf"
else
  COMPILATION_CMD="PKGTOOLS/cmsBuild -i $WORKSPACE/$BUILD_DIR --repository $CMS_WEEKLY_REPO --arch $ARCH -j $(Jenkins_GetCPU) build $PKGS $TOOLFILES"
fi
echo $COMPILATION_CMD > $WORKSPACE/cmsswtoolconf.log
(eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
echo 'END OF BUILD LOG'
echo '--------------------------------------'

RESULTS_FILE=$WORKSPACE/testsResults.txt
touch $RESULTS_FILE

TEST_ERRORS=$(grep -E "Error [0-9]$" $WORKSPACE/cmsswtoolconf.log) || true
GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/cmsswtoolconf.log) || true

if [ "X$TEST_ERRORS" != X ]; then
  ERROR_MSG="Compilation of cmssw-tool-conf failed.\n https://cmssdt.cern.ch/jenkins/job/${JOB_NAME}/${BUILD_NUMBER}/console \n \\
             https://cmssdt.cern.ch/SDT/jenkins-artifacts/${JOB_NAME}/PR-${PULL_REQUEST_NUMBER}/${BUILD_NUMBER}/cmsswtoolconf.log"
  $WORKSPACE/cms-bot/modify_comment.py -r $PUB_REPO -t JENKINS_TEST_URL -m $ERROR_MSG $PULL_REQUEST_NUMBER || true
  echo 'CMSSWTOOLCONF_RESULTS;ERROR' >> $RESULTS_FILE
  exit 0
else
  echo 'CMSSWTOOLCONF_RESULTS;OK' >> $RESULTS_FILE
fi

# Create an appropriate CMSSW area
SCRAM_ARCH=$ARCH
scram project $CMSSW_IB
pushd $CMSSW_IB/src
eval $(scramv1 runtime -sh)

# Setup all the toolfiles previously built
DEP_NAMES=""
for TOOL in $TOOLFILES; do
  if [ -d $WORKSPACE/$BUILD_DIR/$ARCH/external/$TOOL/*/etc/scram.d/ ]; then
    XML=$(find $WORKSPACE/$BUILD_DIR/$ARCH/external/$TOOL/*/etc/scram.d/ -name *.xml)
    for FILE in $XML; do
      scram setup $FILE 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
      DEP_NAMES=$DEP_NAMES" "$(echo $FILE | sed 's|.*/||;s|.xml$||')
    done
  fi
done
eval $(scramv1 runtime -sh)

# Search for CMSSW package that might depend on the compiled externals
CMSSW_DEP=$(for D in $DEP_NAMES; do (for L in $(scram build echo_${D}_USED_BY); do echo $L | grep '\(self\|cmssw\)' | cut -d"/" -f 2,3; done); done)
for DEP in $CMSSW_DEP; do git cms-addpkg $DEP 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log; done

# Launch the standard ru-pr-tests to check CMSSW side passing on the global variables
$WORKSPACE/cms-bot/run-pr-tests
