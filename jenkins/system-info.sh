#!/bin/bash -e
aklog >/dev/null 2>&1 || true
ACTUAL_NPROC=$(getconf _NPROCESSORS_ONLN 2> /dev/null || true)
[ "${ACTUAL_NPROC}" != "" ] || ACTUAL_NPROC=$(nproc)
ACTUAL_MEMORY=$(free -m | grep Mem: | awk '{print $2}')
if [ -d $HOME/bin ] ; then export PATH=$HOME/bin:$PATH ; fi
OVERRIDE_NPROC=$(nproc)
OVERRIDE_MEMORY=$(free -m | grep Mem: | awk '{print $2}')
$(pgrep -a 'proofserv.exe'  | grep '^[1-9][0-9]* ' | sed 's| .*||' | xargs --no-run-if-empty kill -9) || true
for repo in cms cms-ib grid projects unpacked ; do
  ls -l /cvmfs/${repo}.cern.ch >/dev/null 2>&1 || true
done
#cleanup old /tmp files
([ -f /tmp/$(whoami) ] && rm -f /tmp/$(whoami)) || true
([ -d /tmp/$(whoami) ] && touch /tmp/$(whoami)) || true
find /tmp -mindepth 1 -maxdepth 1 -mtime +1 -user $(whoami) -exec rm -rf {} \; || true

SCRIPT_DIR=$(cd $(dirname $0); /bin/pwd)

JENKINS_SLAVE_JAR_MD5="$1"
WORKSPACE="$2"
DOCKER_IMG_HOST="$3"
CLEANUP_WORKSPACE="$4"
USER_HOME_MD5="$5"
if [ "X$WORKSPACE" = "X" ] ; then echo DATA_ERROR="Missing workspace directory." ;        exit 1; fi
if [ ! -e  $HOME ] ;         then echo DATA_ERROR="Home directory $HOME not available." ; exit 1; fi
if [ "${CLEANUP_WORKSPACE}" = "cleanup" ] ; then rm -rf $WORKSPACE ; fi
mkdir -p $WORKSPACE/tmp $WORKSPACE/workspace
rm -f $WORKSPACE/cmsos

#Protection for CVE-2022-24765
#Workaround for lxplus /tmp/.git
if [ $(hostname | grep 'lxplus' | wc -l) -gt 0 ] ; then
  if [ ! -e $WORKSPACE/.git/config ] ; then
    rm -rf $WORKSPACE/.git
    git init $WORKSPACE
  fi
else
  rm -rf $WORKSPACE/.git
fi
git config --global cms.protocol "mixed" || true

#Delete old failed builds
if [ -d ${WORKSPACE}/workspace/auto-builds ] ; then
  for failed in $(find ${WORKSPACE}/workspace/auto-builds -mindepth 2 -maxdepth 2 -name 'BUILD_FAILED' -type f | sed 's|/BUILD_FAILED$||') ; do
    rm -rf ${failed} >/dev/null 2>&1 || true
  done
fi

echo "DATA_SHELL=${SHELL}"

RSYNC_SLAVE=false
if [ "${USER_HOME_MD5}" != "" ] ; then
  RSYNC_SLAVE_FILE="${HOME}/.jenkins_slave_md5"
  if [ ! -f ${RSYNC_SLAVE_FILE} ] ; then
    RSYNC_SLAVE=true
  elif [ $(cat ${RSYNC_SLAVE_FILE}) != "${USER_HOME_MD5}" ] ; then
    RSYNC_SLAVE=true
  else
    HN=$(hostname -s)
    if [ -e "${HOME}/.ssh/authorized_keys-${HN}" ] ; then
      cat ${HOME}/.ssh/authorized_keys-${HN} >> ${HOME}/.ssh/authorized_keys
      rm -f ${HOME}/.ssh/authorized_keys-${HN}
    fi
  fi
fi
echo "DATA_RSYNC_SLAVE=${RSYNC_SLAVE}"

slave_jar=false
if [ -e $WORKSPACE/slave.jar ] ; then
  if [ "$(md5sum $WORKSPACE/slave.jar | sed 's| .*||')" = "$JENKINS_SLAVE_JAR_MD5" ] ; then
    slave_jar=true
  else
    rm -f $WORKSPACE/slave.jar
  fi
fi
echo "DATA_SLAVE_JAR=${slave_jar}"

SLAVE_LABELS="user-$(whoami) kernel-$(uname -r) hostname-$(hostname -s)"
if [ $(echo $HOME | grep '^/afs/' |wc -l) -gt 0 ] ; then SLAVE_LABELS="${SLAVE_LABELS} home-afs"; fi
arch=$(uname -m)
SLAVE_LABELS="${SLAVE_LABELS} ${arch}"
HOST_ARCH=""
if [ "$arch" = "aarch64" ] ; then
  HOST_ARCH=arm$(cat /proc/cpuinfo 2> /dev/null | grep 'CPU architectur' | sed 's|.*: *||' | tail -1)
elif [ "$arch" = "x86_64" ] ; then
  arch="amd64"
  SLAVE_LABELS="${SLAVE_LABELS} ${arch}"
  HOST_ARCH=$(cat /proc/cpuinfo 2> /dev/null | grep vendor_id | sed 's|.*: *||' | tail -1)
fi
echo "DATA_HOST_ARCH=${HOST_ARCH}"
SLAVE_LABELS="${SLAVE_LABELS} ${HOST_ARCH}"

#Check for EOS
[ -e /eos/cms/store ] && SLAVE_LABELS="${SLAVE_LABELS} eos"

DOCKER=""
if docker --version >/dev/null 2>&1 ; then
  if [ $(docker --version 2>&1 | grep -i podman | wc -l) -eq 0 ] ; then
    docker ps >/dev/null 2>&1 || true
    if docker ps >/dev/null 2>&1 ; then
      DOCKER="docker"
      [ -e /var/crash ] && (docker run -u 0:0 -v /var/crash:/tmp/crash --rm -w /tmp alpine:3.16.2 sh -c 'rm -rf /tmp/crash/*' || true)
      if [ -e $HOME/.docker/config.json ] ; then
        SLAVE_LABELS="${SLAVE_LABELS} docker-build"
      fi
    fi
  fi
fi
echo "DATA_DOCKER=${DOCKER}"
SLAVE_LABELS="${SLAVE_LABELS} ${DOCKER}"

SINGULARITY=""
if singularity --version >/dev/null 2>&1 ; then
  if [ -e /proc/sys/user/max_user_namespaces ] ; then
    if [ $(cat /proc/sys/user/max_user_namespaces) -gt 0 ] ; then
      SINGULARITY="singularity"
    fi
  else
    SINGULARITY="singularity"
  fi
fi
echo "DATA_SINGULARITY=${SINGULARITY}"
SLAVE_LABELS="${SLAVE_LABELS} ${SINGULARITY}"

if [ "${DOCKER}${SINGULARITY}" != "" ] && [ "$DOCKER_IMG_HOST" != "" ] ; then
  os=$(echo $DOCKER_IMG_HOST | sed 's|:.*||;s|.*/||;s|-.*||')
  SLAVE_LABELS="${SLAVE_LABELS} ${os}"
  if [ "$os" = "cc7" ] ; then os="slc7" ; fi
  HOST_CMS_ARCH=${os}_${arch}
else
  rm -f $WORKSPACE/cmsos
  curl -s -k -L -o $WORKSPACE/cmsos https://raw.githubusercontent.com/cms-sw/cms-common/master/common/cmsos
  chmod +x $WORKSPACE/cmsos
  HOST_CMS_ARCH=$($WORKSPACE/cmsos 2>/dev/null)
fi
echo "DATA_SYSTEM_LOAD=$(uptime | sed 's|.*: *||;s|, *|:|g')"
echo "DATA_HOST_CMS_ARCH=${HOST_CMS_ARCH}"
SLAVE_LABELS="${SLAVE_LABELS} ${HOST_CMS_ARCH} $(echo ${HOST_CMS_ARCH} | tr _ ' ')"

echo "DATA_REMOTE_USER_ID=$(id -u)"

let WORKSPACE_SIZE="$(df -k ${WORKSPACE} | tail -1 | tr ' ' '\n' | grep -v '^$' | tail -3 | head -1)/(1024*1024)" || true
echo "DATA_WORKSPACE_SIZE=${WORKSPACE_SIZE}"

JENKINS_SLAVE_SETUP=false
if [ -f ~/.jenkins-slave-setup ] ; then JENKINS_SLAVE_SETUP=true ; fi
echo "DATA_JENKINS_SLAVE_SETUP=${JENKINS_SLAVE_SETUP}"

echo "DATA_ACTUAL_CPUS=${ACTUAL_NPROC}"
echo "DATA_ACTUAL_MEMORY=${ACTUAL_MEMORY}"
SLAVE_LABELS="${SLAVE_LABELS} real-cpu-${ACTUAL_NPROC} real-memory-${ACTUAL_MEMORY}"
echo "DATA_CPUS=${OVERRIDE_NPROC}"
echo "DATA_MEMORY=${OVERRIDE_MEMORY}"
SLAVE_LABELS="${SLAVE_LABELS} cpu-${OVERRIDE_NPROC} cpu-tiny memory-${OVERRIDE_MEMORY}"
for t in 2:small 4:medium 8:large 16:xlarge 24:x2large 32:x3large 64:huge; do
  c=$(echo $t | sed 's|:.*||')
  if [ ${OVERRIDE_NPROC} -ge $c ] ; then SLAVE_LABELS="${SLAVE_LABELS} cpu-$(echo $t | sed 's|.*:||')" ; fi
done

CPU_VECTOR_SET=$(cat /proc/cpuinfo | grep '^flags' | tail -1 | tr ' ' '\n' | grep '^sss*e\|^avx' | tr '\n' ' ')
echo "DATA_CPU_VECTOR_SET=${CPU_VECTOR_SET}"SINGULARITY
for is in ${CPU_VECTOR_SET} ; do SLAVE_LABELS="${SLAVE_LABELS} is-${is}" ; done

if [ -f /proc/driver/nvidia/version ]; then
  NVIDIA_VERSION=`cat /proc/driver/nvidia/version | sed -ne's/.*Kernel Module *\([0-9.]\+\).*/\1/p'`
else 
  # check if a kernel module is available, even if not currently loaded (e.g. for an OPTIMUS system)
  # if there are multiple modules, pick the newest one
  NVIDIA_MODULE=`modprobe -q -R nvidia 2>/dev/null || true`
  if [ "$NVIDIA_MODULE" ]; then
    NVIDIA_VERSION=`modinfo "$NVIDIA_MODULE" | grep '^version:' | sed 's|.*:\s*||;s|\s*$||'`
  fi
fi
echo "DATA_NVIDIA_VERSION=$NVIDIA_VERSION"
if [ "$NVIDIA_VERSION" ]; then SLAVE_LABELS="${SLAVE_LABELS} nvidia nvidia-$NVIDIA_VERSION" ; fi

if [ $(hostname | grep 'lxplus' | wc -l) -gt 0 ] ; then
  hname=$(hostname -s)
  case ${HOST_CMS_ARCH} in
    slc6_*) lxplus_type="lxplus6";;
    slc7_*|cc7_*|cs7_*) lxplus_type="lxplus7";;
    cc8_*|cs8_*|el8_*) lxplus_type="lxplus8";;
    cs9_*|el9_*) lxplus_type="lxplus9";;
  esac
  if [ "${CLEANUP_WORKSPACE}" != "cleanup" ] ; then
    SLAVE_LABELS="$hname lxplus-scripts ${lxplus_type}-scripts ${SLAVE_LABELS}"
  else 
    SLAVE_LABELS="$hname lxplus ${lxplus_type} ${SLAVE_LABELS}"
  fi
fi

#Search for Hard limits
val=""
if [ $(echo "${SHELL}" | grep '/csh\|/tcsh' | wc -l) -eq 0 ] ; then
  for o in n s u ; do
    val="-$o $(ulimit -H -$o) ${val}"
  done
fi
echo "DATA_LIMITS=${val}"

#Extra labels
case $(hostname -s) in
  techlab-arm64-thunderx-02 | ibmminsky-* ) SLAVE_LABELS="profiling ${SLAVE_LABELS}";;
esac
SLAVE_LABELS="disk-$(df -BG $WORKSPACE | tail -1 | awk '{print $2"-"$4}') ${SLAVE_LABELS}"
echo "DATA_SLAVE_LABELS=$(echo ${SLAVE_LABELS} | tr ' ' '\n' | grep -v '^$' | sort | uniq | tr '\n' ' ')"
