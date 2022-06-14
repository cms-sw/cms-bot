#!/bin/bash -x
# Retry a command with exponential backoff
# Source: https://gist.github.com/askoufis/0da8502b5f1df4d067502273876fcd07
function retry {
  local maxAttempts=$1
  local secondsDelay=1
  local attemptCount=1
  local output=
  shift 1

  while [ $attemptCount -le $maxAttempts ]; do
    output=$("$@")
    local status=$?

    if [ $status -eq 0 ]; then
      break
    fi

    if [ $attemptCount -lt $maxAttempts ]; then
      echo "Command [$@] failed after attempt $attemptCount of $maxAttempts. Retrying in $secondsDelay second(s)." >&2
      sleep $secondsDelay
    elif [ $attemptCount -eq $maxAttempts ]; then
      echo "Command [$@] failed after $attemptCount attempt(s)" >&2
      return $status;
    fi
    attemptCount=$(( $attemptCount + 1 ))
    secondsDelay=$(( $secondsDelay * 2 ))
  done

  echo $output
}

if [ `uname` == "Darwin" ]; then
    CORES=`sysctl -n hw.ncpu`
elif [ `uname` == "Linux" ]; then
    CORES=`awk '/^processor/ { N++} END { print N }' /proc/cpuinfo`
fi
export CORES
echo Setup Spack for CMS
cd $WORKSPACE

# For boto3
export PYTHONPATH=/cvmfs/cms-ib.cern.ch/share/python3/lib/python3.6/site-packages:$PYTHONPATH

export S3_ENDPOINT_URL=https://s3.cern.ch
export SPACK_DISABLE_LOCAL_CONFIG=true
export SPACK_USER_CACHE_PATH=$WORKSPACE
cd spack
echo Add signing key
if [ ! -z ${SPACK_GPG_KEY+x} ]; then
  if [ -e ${SPACK_GPG_KEY} ]; then
    bin/spack gpg trust $SPACK_GPG_KEY
  else
    echo ERROR: GPG key not found
    touch ${WORKSPACE}/fail
    exit 1
  fi
fi

echo Setup spack
. share/spack/setup-env.sh
echo Add padding to install_tree
bin/spack config add "config:install_tree:padded_length:128"
echo Set local monitor directory
bin/spack config add "config:monitor_dir:$WORKSPACE/monitor"
echo Start the installation
# bin/spack env activate ${SPACK_ENV_NAME}
# bin/spack -e ${SPACK_ENV_NAME} -d --show-cores=minimized concretize
SPACK_MON_ARGS="--monitor --monitor-save-local"
#export SPACKMON_USER="cmsbuild"
#if [ ! -z ${SPACKMON_TOKEN} ]; then SPACK_MON_ARGS="--monitor --monitor-save-local --monitor-tags ${SPACK_ENV_NAME}"; export SPACKMON_TOKEN; fi;
bin/spack --show-cores=minimized -e ${SPACK_ENV_NAME} install --show-log-on-error --require-full-hash-match -j$CORES --fail-fast $SPACK_MON_ARGS
exit_code=$?
if [ ${exit_code} -ne 0 ]; then
    touch $WORKSPACE/fail
    exit ${exit_code}
fi
echo build.sh done
