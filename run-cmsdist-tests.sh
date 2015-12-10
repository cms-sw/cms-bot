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
if(( $(cat $WORKSPACE/cms-bot/config.map | grep $CMSDIST_BRANCH | wc -l) > 1 )); then
  CMSSW_CYCLE=$(cat $WORKSPACE/cms-bot/config.map | grep $CMSDIST_BRANCH | grep "PROD_ARCH" | cut -d ";" -f 4 | cut -d "=" -f 2)
else
  CMSSW_CYCLE=$(cat $WORKSPACE/cms-bot/config.map | grep $CMSDIST_BRANCH | cut -d ";" -f 4 | cut -d "=" -f 2)
fi

CMSSW_IB=$(scram l $CMSSW_CYCLE | grep -v /ReleaseCandidates | tail -n 1 | awk '{print $2}')

if [ "X$TEST_USER" = "X" ] || [ "X$TEST_BRANCH" = "X" ]; then
  echo "Error: failed to retrieve user or branch to test."
  exit 0
fi

if [ "X$ARCH" == X ]; then
  if(( $(cat $WORKSPACE/cms-bot/config.map | grep $CMSDIST_BRANCH | wc -l) > 1 )); then
    ARCH=$(cat $WORKSPACE/cms-bot/config.map | grep $CMSDIST_BRANCH | grep PR_TESTS | cut -d ";" -f 1 | cut -d "=" -f 2)
  else
    ARCH=$(cat $WORKSPACE/cms-bot/config.map | grep $CMSDIST_BRANCH | cut -d ";" -f 1 | cut -d "=" -f 2)
  fi
fi

if [ "X$PKGTOOLS_BRANCH" == X ]; then
  PKGTOOLS_BRANCH="V00-22-XX"
fi

BUILD_DIR="testBuildDir"
export PUB_REPO="cms-sw/cmsdist"

$WORKSPACE/cms-bot/modify_comment.py -r $PUB_REPO -t JENKINS_TEST_URL -m "https://cmssdt.cern.ch/jenkins/job/${JOB_NAME}/${BUILD_NUMBER}/console" $CMSDIST_PR || true
# If a CMSSW PR is also being tested update the comment on its page too
if [ "X$PULL_REQUEST" != X ]; then
  $WORKSPACE/cms-bot/modify_comment.py -r cms-sw/cmssw -t JENKINS_TEST_URL -m "https://cmssdt.cern.ch/jenkins/job/${JOB_NAME}/${BUILD_NUMBER}/console" $PULL_REQUEST || true
fi

git clone git@github.com:cms-sw/cmsdist $WORKSPACE/CMSDIST -b $CMSDIST_BRANCH
git clone git@github.com:cms-sw/pkgtools $WORKSPACE/PKGTOOLS -b $PKGTOOLS_BRANCH

cd $WORKSPACE/CMSDIST
git pull git://github.com/$TEST_USER/cmsdist.git $TEST_BRANCH
# Check which packages the PR changes
PKGS=$(git diff origin/$CMSDIST_BRANCH.. --name-only --diff-filter=ACMR | grep -v .patch | cut -d"." -f"1")

export CMSDIST_COMMIT=$(git log origin/$CMSDIST_BRANCH.. --pretty="%H" --no-merges | head -n 1)
cd $WORKSPACE

# Notify github that the script will start testing now
$WORKSPACE/cms-bot/report-pull-request-results TESTS_RUNNING --repo $PUB_REPO --pr $CMSDIST_PR -c $CMSDIST_COMMIT --pr-job-id ${BUILD_NUMBER} $DRY_RUN

# Build the whole cmssw-tool-conf toolchain
COMPILATION_CMD="PKGTOOLS/cmsBuild -i $WORKSPACE/$BUILD_DIR --repository $CMS_WEEKLY_REPO  --arch $ARCH -j $(Jenkins_GetCPU) build cmssw-tool-conf"
echo $COMPILATION_CMD > $WORKSPACE/cmsswtoolconf.log
(eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
echo 'END OF BUILD LOG'
echo '--------------------------------------'

RESULTS_FILE=$WORKSPACE/testsResults.txt
touch $RESULTS_FILE

TEST_ERRORS=$(grep -E "Error [0-9]$" $WORKSPACE/cmsswtoolconf.log) || true
GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/cmsswtoolconf.log) || true

if [ "X$TEST_ERRORS" != X ] || [ "X$GENERAL_ERRORS" == X ]; then
  $WORKSPACE/cms-bot/report-pull-request-results PARSE_BUILD_FAIL --repo $PUB_REPO --pr $CMSDIST_PR -c $CMSDIST_COMMIT --pr-job-id ${BUILD_NUMBER} --unit-tests-file $WORKSPACE/cmsswtoolconf.log
  echo 'PR_NUMBER;'$CMSDIST_PR >> $RESULTS_FILE
  echo 'ADDITIONAL_PRS;'$ADDITIONAL_PULL_REQUESTS >> $RESULTS_FILE
  echo 'BASE_IB;'$CMSSW_IB >> $RESULTS_FILE
  echo 'BUILD_NUMBER;'$BUILD_NUMBER >> $RESULTS_FILE
  echo 'CMSSWTOOLCONF_RESULTS;ERROR' >> $RESULTS_FILE
  # creation of results summary file, normally done in run-pr-tests, here just to let close the process
  cp $WORKSPACE/cms-bot/templates/PullRequestSummary.html $WORKSPACE/summary.html
  cp $WORKSPACE/cms-bot/templates/js/renderPRTests.js $WORKSPACE/renderPRTests.js
  exit 0
else
  echo 'CMSSWTOOLCONF_RESULTS;OK' >> $RESULTS_FILE
fi

# Create an appropriate CMSSW area
SCRAM_ARCH=$ARCH
scram project $CMSSW_IB
pushd $CMSSW_IB/src

# Setup all the toolfiles previously built
mv ../config/toolbox/${ARCH}/tools/selected ../config/toolbox/${ARCH}/tools/selected.old
cp -r $WORKSPACE/$BUILD_DIR/$ARCH/cms/cmssw-tool-conf/*/tools/selected  ../config/toolbox/${ARCH}/tools/selected
scram setup
DEP_NAMES=""
for DIR in `find $WORKSPACE/$BUILD_DIR/BUILD/$ARCH -maxdepth 3 -mindepth 3 -type d | sed "s|/BUILD/$ARCH/|/$ARCH/|"` ; do
  if [ -d $DIR/etc/scram.d ]; then
    for FILE in `find $DIR/etc/scram.d -name '*.xml'`; do
      DEP_NAMES=$DEP_NAMES" echo_"$(echo $FILE | sed 's|.*/||;s|.xml$||')"_USED_BY"
    done
  fi
done
eval $(scram runtime -sh)

# Search for CMSSW package that might depend on the compiled externals
CMSSW_DEP=$(scram build ${DEP_NAMES} | tr ' ' '\n' | grep '^cmssw/' | cut -d"/" -f 2,3 | sort | uniq)
git cms-addpkg $CMSSW_DEP 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log

# Launch the standard ru-pr-tests to check CMSSW side passing on the global variables
$WORKSPACE/cms-bot/run-pr-tests
