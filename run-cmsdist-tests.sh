#!/bin/sh -ex

if [ "X$TEST_PR" == X ]; then
  echo "Error: TEST_PR variable must be set"
  exit 0
fi

GH_JSON=$(curl -s https://api.github.com/repos/cms-sw/cmsdist/pulls/$TEST_PR)
TEST_USER=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["repo"]["owner"]["login"]')
TEST_BRANCH=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["ref"]')

if [ "X$TEST_USER" == X ] || [ "X$TEST_BRANCH" == X]; then
  echo "Error: failed to retrieve user or branch to test."
  exit 0
fi

if [ "X$ARCH" == X ]; then
  ARCH="slc6_amd64_gcc493"
fi

if [ "X$CMSDIST_BRANCH" == X ]; then
  CMSDIST_BRANCH="IB/CMSSW_8_0_X/stable"
fi

if [ "X$PKGTOOLS_BRANCH" == X ]; then
  PKGTOOLS_BRANCH="V00-22-XX"
fi

if [ "X$MATRIX_EXTRAS" == X ]; then
  MATRIX_EXTRAS="1306.0,101.0,1003.0,50202.0,9.0,25202.0"
fi

if [ "X$MATRIX_TIMEOUT" == X ]; then
  MATRIX_TIMEOUT="9000"
fi

BUILD_DIR="testBuildDir"

git clone git@github.com:cms-sw/cmsdist $WORKSPACE/CMSDIST -b $CMSDIST_BRANCH
git clone git@github.com:cms-sw/pkgtools $WORKSPACE/PKGTOOLS -b $PKGTOOLS_BRANCH

cd $WORKSPACE/CMSDIST
git pull git://github.com/$TEST_USER/cmsdist.git $TEST_BRANCH
# Check which packages the PR changes
PKGS=$(git diff  ..origin/$CMSDIST_BRANCH --name-only | cut -d"." -f"1")

# Check if the packages have a toolfile and add them to the build if they exists
for P in $PKGS; do
  if [ -f $P-toolfile.spec ]; then
    TOOLFILES=$TOOLFILES" "$P-toolfile
  fi
done
cd $WORKSPACE

# Build the whole cmssw-tool-conf toolchain
COMPILATION_CMD="PKGTOOLS/cmsBuild -i $BUILD_DIR --arch $ARCH -j $(Jenkins_GetCPU) build cmssw-tool-conf"
echo $COMPILATION_CMD > $WORKSPACE/cmsswtoolconf.log
(eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
echo 'END OF BUILD LOG'
echo '--------------------------------------'

TEST_ERRORS=$(grep -E "^gmake: .* Error [0-9]" $WORKSPACE/cmsswtoolconf.log) || true
GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/cmsswtoolconf.log) || true

if [ "X$TEST_ERRORS" != "X" ] || [ "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors when building cmssw-tool-conf"
  $WORKSPACE/cms-bot/report-pull-request-results PARSE_BUILD_FAIL --repo cmsdist --pr $PULL_REQUEST_NUMBER --pr-job-id ${BUILD_NUMBER} --unit-tests-file $WORKSPACE/cmsswtoolconf.log --add-message "Cmssw-tool-conf compilation failed" $DRY_RUN
  exit 0
fi


# Create an appropriate CMSSW area
CMSSW_IB=$(scram l $(echo $CMSDIST_BRANCH | cut -d"/" -f 2) | grep -v /ReleaseCandidates | tail -n 1 | awk '{print $2}')
SCRAM_ARCH=$ARCH
scram project $CMSSW_IB
pushd $CMSSW_IB/src
eval $(scramv1 runtime -sh)

# Setup all the toolfiles previously built
for TOOL in $TOOLFILES; do
  scram setup ../../$BUILD_DIR/$ARCH/external/$TOOL/*/etc/scram.d/*.xml
done
eval $(scramv1 runtime -sh)

# Search for CMSSW package that might depend on the compiled externals
CMSSW_DEP=$(for P in $PKGS; do (for L in $(scram build echo_${P}_USED_BY); do echo $L | grep '\(self\|cmssw\)' | cut -d"/" -f 2,3; done); done)
for DEP in $CMSSW_DEP; do git cms-addpkg $DEP; done

# If there is a CMSSW PR to check alongside merge it
if [ "X$CMSSW_PR" != X ]; then
  git cms-merge-topic $CMSSW_PR
fi

# Build all the packages added
COMPILATION_CMD="scram build -j $(Jenkins_GetCPU)"
echo $COMPILATION_CMD > $WORKSPACE/cmsswpkgs.log
(eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/cmsswpkgs.log
echo 'END OF BUILD LOG'
echo '--------------------------------------'

TEST_ERRORS=$(grep -E "^gmake: .* Error [0-9]" $WORKSPACE/cmsswpkgs.log) || true
GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/cmsswpkgs.log) || true

if [ "X$TEST_ERRORS" != "X" ] || [ "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors when building cmssw packages dependency"
  $WORKSPACE/cms-bot/report-pull-request-results PARSE_BUILD_FAIL --repo cmsdist --pr $PULL_REQUEST_NUMBER --pr-job-id ${BUILD_NUMBER} --unit-tests-file $WORKSPACE/cmsswpkgs.log --add-message "Cmssw packages compilation failed" $DR$
  exit 0
fi
popd

# Run usual relvals
EXTRA_RELVALS_OPTION=""
if [[ $CMSSW_IB != CMSSW_5_3_X* ]] && [ "X$USE_DAS_CACHE" = Xtrue ]; then
  wget --no-check-certificate https://raw.githubusercontent.com/cms-sw/cmsdist/HEAD/das-cache.file
  EXTRA_RELVALS_OPTION='--das-options="--cache das-cache.file --limit 0"'
fi

RELVALS_CMD="timeout $MATRIX_TIMEOUT runTheMatrix.py $EXTRA_RELVALS_OPTION -j $(Jenkins_GetCPU) -s -l $MATRIX_EXTRAS"
echo $RELVALS_CMD > matrixTests.log
(eval $RELVALS_CMD && echo 'ALL_OK') 2>&1 | tee -a matrixTests.log
echo 'END OF BUILD LOG'
echo '--------------------------------------'

TEST_ERRORS=$(grep -i -E "ERROR .*" $WORKSPACE/matrixTests.log) || true
GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/matrixTests.log) || true

if [ "X$TEST_ERRORS" != "X" ] || [ "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors running relvals"
  $WORKSPACE/cms-bot/report-pull-request-results PARSE_MATRIX_FAIL --repo cmsdist --pr $PULL_REQUEST_NUMBER --pr-job-id ${BUILD_NUMBER} --unit-tests-file $WORKSPACE/matrixTests.log $DRY_RUN
  exit 0
fi
# All is good
$WORKSPACE/cms-bot/report-pull-request-results TESTS_OK_PR --repo cmsdist --pr $PULL_REQUEST_NUMBER --pr-job-id ${BUILD_NUMBER} $DRY_RUN
