#!/bin/bash -ex

[ "${WORKSPACE}" = "" ] && export WORKSPACE=$(/bin/pwd -P)
INSTALL_SCRIPT="$1"
CMSSW_CONFIG_TAG="$2"
EXTRA_PRS="$3"
CLANG_TIDY="$4"
CLANG_FORMAT="$5"
TEST_CHANGES="$6"
[ "${CLANG_TIDY}"   != "true" ] && CLANG_TIDY=false
[ "${CLANG_FORMAT}" != "true" ] && CLANG_FORMAT=false
[ "${TEST_CHANGES}" != "true" ] && TEST_CHANGES=false

mkdir $WORKSPACE/upload
if [ "${INSTALL_SCRIPT}" != "" ] ; then
  ${INSTALL_SCRIPT}
  CMSSW_PROJECT=$(ls -d CMSSW_*)
  export SCRAM_ARCH=$(ls -d ${CMSSW_PROJECT}/lib/* | sed 's|.*/||')
  cd $CMSSW_PROJECT
  rm -rf src; mkdir src
  scram build clean
else
  eval $(grep 'RELEASE_BRANCH=master;' cms-bot/config.map | grep PROD_ARCH=1 )
  export SCRAM_ARCH
  CMSSW_PROJECT=$(scram -a $SCRAM_ARCH l -c $RELEASE_QUEUE | tr -s ' ' |  cut -d ' '   -f2 | tail -n 1)
  scram -a ${SCRAM_ARCH} project ${CMSSW_PROJECT}
  cd $CMSSW_PROJECT
fi
if [ "${CMSSW_CONFIG_TAG}" != "" ] ; then
  git clone git@github.com:cms-sw/cmssw-config
  pushd cmssw-config ; git checkout ${CMSSW_CONFIG_TAG} ; popd
  rm -rf config/SCRAM
  mv cmssw-config/SCRAM config/SCRAM
  rm -rf cmssw-config
fi
pwd
set +x ; eval `scram runtime -sh` ; set -x
echo $CMSSW_BASE
NUM_PROC=$(nproc)
pushd src
  git cms-addpkg '*'
  git checkout $(git branch | grep  '^  *CMSSW_')
  for pr in ${EXTRA_PRS} ; do
    git cms-merge-topic -u ${pr}
  done
popd
#Keep original sources to be used by clang-format
rsync -a src src.orig

$CMSSW_BASE/config/SCRAM/find-extensions.sh -t $CMSSW_BASE
cat $CMSSW_BASE/selected-source-files.txt | grep -v '/test/' > $CMSSW_BASE/selected-source-files.txt.filtered || true

ERR=0
if $CLANG_TIDY ; then
  scram build -k -j ${NUM_PROC} code-checks-all USER_CODE_CHECKS_FILE=$CMSSW_BASE/selected-source-files.txt.filtered  > $WORKSPACE/upload/code-checks.log 2>&1 || ERR=1
  pushd src
    git diff --name-only > $WORKSPACE/upload/code-checks.txt
    git diff > $WORKSPACE/upload/code-checks.patch
  popd
  cat $WORKSPACE/upload/code-checks.patch
  echo "Files need clang-tidy fixes ....."
  cat $WORKSPACE/upload/code-checks.txt
  cat $WORKSPACE/upload/code-checks.txt | wc -l
  cat $WORKSPACE/upload/code-checks.txt | cut -d/ -f1,2 | sort | uniq
  cat $WORKSPACE/upload/code-checks.txt | cut -d/ -f1,2 | sort | uniq > $WORKSPACE/upload/code-checks-pkgs.log
else
  touch $WORKSPACE/upload/code-checks.txt
fi

if $CLANG_FORMAT ; then
  mv src src.tidy
  mv src.orig src
  scram build -k -j ${NUM_PROC} code-format-all > $WORKSPACE/upload/code-format-orig.log 2>&1 || ERR=1
  pushd src
    git diff --name-only > $WORKSPACE/upload/code-format-orig.txt
    git diff > $WORKSPACE/upload/code-format-orig.patch
  popd
  cat $WORKSPACE/upload/code-format-orig.txt | cut -d/ -f1,2 | sort | uniq > $WORKSPACE/upload/code-format-pkgs-orig.log
  mv src src.format
  mv src.tidy src
  scram build -k -j ${NUM_PROC} code-format-all > $WORKSPACE/upload/code-format.log 2>&1 || ERR=1
  pushd
    git diff --name-only > $WORKSPACE/upload/code-format.txt
    git diff > $WORKSPACE/upload/code-format.patch
  popd
  cat $WORKSPACE/upload/code-format.txt | cut -d/ -f1,2 | sort | uniq > $WORKSPACE/upload/code-format-pkgs.log  
else
  touch $WORKSPACE/upload/code-format.txt
fi

echo "All files Changed"
cat $WORKSPACE/upload/code-checks.txt $WORKSPACE/upload/code-format.txt | sort | uniq > $WORKSPACE/upload/code-format.txt
cat $WORKSPACE/upload/code-format.txt | cut -d/ -f1,2 | sort | uniq > $WORKSPACE/upload/code-all-pkgs.log

if $TEST_CHANGES ; then
  echo "Running scram build"
  scram build clean
  BUILD_LOG=yes SCRAM_NOEDM_CHECKS=yes scram build -k -j ${NUM_PROC} 2>&1 > $WORKSPACE/upload/build.log || true
  scram build outputlog || true
  BUILD_LOG_DIR="${CMSSW_BASE}/tmp/${SCRAM_ARCH}/cache/log"
  $WORKSPACE/cms-bot/buildLogAnalyzer.py --logDir ${BUILD_LOG_DIR}/src || true
  [ -d ${BUILD_LOG_DIR}/html ] && mv ${BUILD_LOG_DIR}/html $WORKSPACE/upload/build-logs
fi
