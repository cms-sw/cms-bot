#!/bin/bash -ex
if [ "${USER}" = "" ] ; then export USER=$(whoami); fi
if [ "${HOME}" = "" ] ; then
  if [ "${_CONDOR_SCRATCH_DIR}" != "" ] ; then export HOME="${_CONDOR_SCRATCH_DIR}" ; fi
fi
if [ "X$ADDITIONAL_TEST_NAME" = "Xigprof" ] ; then
  if ulimit -a ; then
    ulimit -n 4096 -s 81920
    ulimit -a
  fi
else
  if ulimit -a ; then
    opts=""
    for o in n s u ; do
      opts="-$o $(ulimit -H -$o) ${opts}"
    done
    ulimit ${opts}
    ulimit -a
  fi
fi
export DBS_URL=https://cmsweb.cern.ch:8443/dbs/prod/global/DBSReader
export GIT_CONFIG_NOSYSTEM=1
XPATH=""
py3or2_dir="$HOME/bin"
if [ ! -e ${py3or2_dir} ] ; then
  py3or2_dir="/afs/cern.ch/user/$(whoami | cut -c1)/$(whoami)/bin"
fi
if [ -e ${py3or2_dir} ] ; then
  XPATH="${py3or2_dir}:"
  [ $(echo $PATH | tr ':' '\n' | grep "^${py3or2_dir}$" | wc -l) -eq 0 ] && export PATH="${py3or2_dir}:${PATH}"
fi
if [ "${USE_SINGULARITY}" != "false" ] ; then export USE_SINGULARITY=true; fi
kinit -R || true
aklog || true
for repo in cms cms-ib grid projects unpacked ; do
  ls -l /cvmfs/${repo}.cern.ch >/dev/null 2>&1 || true
done
RUN_NATIVE=
if [ "${RUCIO_ACCOUNT}" = "" ] ; then export RUCIO_ACCOUNT="cmsbot" ; fi
if [ "X$DOCKER_IMG" = "X" -a "$DOCKER_IMG_HOST" != "X" ] ; then DOCKER_IMG=$DOCKER_IMG_HOST ; fi
if [ "X$NOT_RUN_DOCKER" != "X" -a "X$DOCKER_IMG" != "X"  ] ; then
  RUN_NATIVE=`echo $DOCKER_IMG | grep "$NOT_RUN_DOCKER"`
fi
UNAME_M=$(uname -m)
if [ "X$DOCKER_IMG" != X -a "X$RUN_NATIVE" = "X" ]; then
  if [ $(echo "${DOCKER_IMG}" | grep '^cmssw/' | wc -l) -gt 0 ] ; then
    if [ $(echo "${DOCKER_IMG}" | grep ':' | wc -l) -eq 0 ] ; then
      export DOCKER_IMG="${DOCKER_IMG}:${UNAME_M}"
    fi
  fi
  if [ "X$WORKSPACE" = "X" ] ; then export WORKSPACE=$(/bin/pwd) ; fi
  BUILD_BASEDIR=$(dirname $WORKSPACE)
  export KRB5CCNAME=$(klist | grep 'Ticket cache: FILE:' | sed 's|.* ||')
  MOUNT_POINTS="/cvmfs,/tmp,$(echo $WORKSPACE | cut -d/ -f1,2),/var/run/user,/run/user,/etc/pki/ca-trust"
  for xdir in /cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security /cvmfs/grid.cern.ch/etc/grid-security/vomses:/etc/vomses ; do
    ldir=$(echo $xdir | sed 's|.*:||')
    if [ $(echo "${IGNORE_MOUNTS}" | tr ' ' '\n' | grep "^${ldir}$" | wc -l) -gt 0 ] ; then
      continue
    fi
    MOUNT_POINTS="$MOUNT_POINTS,${xdir}"
  done
  if [ $(echo $HOME |  grep '^/home/' | wc -l)  -gt 0 ] ; then
    MOUNT_POINTS="$MOUNT_POINTS,/home"
  fi
  IMG_OS=$(echo $DOCKER_IMG | sed 's|.*/||;s|:.*||')
  XUSER=`whoami`
  AFS_HOME="/afs/cern.ch/user/$(echo ${XUSER} | cut -c1)/${XUSER}"
  if [ -e ${HOME}/.ssh/${IMG_OS} ] ; then
    MOUNT_POINTS="$MOUNT_POINTS,${HOME}/.ssh/${IMG_OS}:${HOME}/.ssh"
  elif [ -e ${AFS_HOME}/.ssh/${IMG_OS} ] ; then
    MOUNT_POINTS="$MOUNT_POINTS,${AFS_HOME}/.ssh/${IMG_OS}:${AFS_HOME}/.ssh"
  fi
  if [ -d /afs/cern.ch ] ; then MOUNT_POINTS="${MOUNT_POINTS},/afs"; fi
  for tnsnames in /etc/tnsnames.ora ${HOME}/tnsnames.ora ; do
    if [ -e "${tnsnames}" ] ; then
      if [ $(echo ${tnsnames} | grep '^/afs/' | wc -l) -gt 0 ] ; then
        cp ${tnsnames} ${WORKSPACE}/
        tnsnames="${WORKSPACE}/tnsnames.ora"
      fi
      MOUNT_POINTS="${MOUNT_POINTS},${tnsnames}:/etc/tnsnames.ora"
      break
    fi
  done
  HAS_DOCKER=false
  if [ "X$USE_SINGULARITY" != "Xtrue" ] ; then
    if [ $(id -Gn 2>/dev/null | grep docker | wc -l) -gt 0 ] ; then
      HAS_DOCKER=$(docker --version >/dev/null 2>&1 && echo true || echo false)
    fi
  fi
  CMD2RUN="export PATH=${XPATH}\$PATH:/usr/sbin;"
  if [ -d $HOME/bin ] ; then
    CMD2RUN="${CMD2RUN}export PATH=\$HOME/bin:\$PATH; "
  fi
  CMD2RUN="${CMD2RUN}voms-proxy-init -voms cms -rfc -valid 24:00 -out $WORKSPACE/x509up_u`id -u` || true ; voms-proxy-info || true; echo \$HOME; cd $WORKSPACE; echo \$PATH; $@"
  if $HAS_DOCKER ; then
    docker pull $DOCKER_IMG
    set +x
    DOCKER_OPT="-e USER=$XUSER"
    case $XUSER in
      cmsbld ) DOCKER_OPT="${DOCKER_OPT} -u $(id -u):$(id -g) -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group" ;;
    esac
    export X509_USER_PROXY=$WORKSPACE/x509up_u`id -u`
    for e in $DOCKER_JOB_ENV GIT_CONFIG_NOSYSTEM WORKSPACE BUILD_URL BUILD_NUMBER JOB_NAME NODE_NAME NODE_LABELS DOCKER_IMG RUCIO_ACCOUNT X509_USER_PROXY; do DOCKER_OPT="${DOCKER_OPT} -e $e"; done
    if [ "${PYTHONPATH}" != "" ] ; then DOCKER_OPT="${DOCKER_OPT} -e PYTHONPATH" ; fi
    for m in $(echo $MOUNT_POINTS,/etc/localtime,${BUILD_BASEDIR},/home/$XUSER | tr ',' '\n') ; do
      x=$(echo $m | sed 's|:.*||')
      [ -e $x ] || continue
      if [ $(echo $m | grep ':' | wc -l) -eq 0 ] ; then m="$m:$m";fi
      DOCKER_OPT="${DOCKER_OPT} -v $m"
    done
    if [ "X$KRB5CCNAME" != "X" ] ; then DOCKER_OPT="${DOCKER_OPT} -e KRB5CCNAME=$KRB5CCNAME" ; fi
    set -x
    echo "Passing to docker the args: "$CMD2RUN
    if [ $(docker run --help | grep '\-\-init ' | wc -l) -gt 0 ] ; then
      DOCKER_OPT="--init $DOCKER_OPT"
    fi
    docker run --rm --net=host $DOCKER_OPT $DOCKER_IMG sh -c "$CMD2RUN"
  else
    ws=$(echo $WORKSPACE |  cut -d/ -f1-2)
    CLEAN_UP_CACHE=false
    DOCKER_IMGX=""
    if [ -e /cvmfs/singularity.opensciencegrid.org/$DOCKER_IMG ] ; then
      DOCKER_IMGX=/cvmfs/singularity.opensciencegrid.org/$DOCKER_IMG
    elif [ -e /cvmfs/unpacked.cern.ch/registry.hub.docker.com/$DOCKER_IMG ] ; then
      DOCKER_IMGX=/cvmfs/unpacked.cern.ch/registry.hub.docker.com/$DOCKER_IMG
    fi
    if [ "$DOCKER_IMGX" = "" ] ; then
      DOCKER_IMGX="docker://$DOCKER_IMG"
      if test -w ${BUILD_BASEDIR} ; then
        export SINGULARITY_CACHEDIR="${BUILD_BASEDIR}/.singularity"
      else
        CLEAN_UP_CACHE=true
        export SINGULARITY_CACHEDIR="${WORKSPACE}/.singularity"
      fi
      mkdir -p $SINGULARITY_CACHEDIR
      export APPTAINER_CACHEDIR="${SINGULARITY_CACHEDIR}"
    fi
    EX_OPTIONS="${SINGULARITY_OPTIONS} ${APPTAINER_OPTIONS}"
    if [ "${CHECK_NVIDIA}" != "false" -a -e "/proc/driver/nvidia/version" ] ; then
      nvidia-smi || true
      cat /proc/driver/nvidia/version || true
      if [ $(echo "${EX_OPTIONS}" | tr ' ' '\n' | grep '^\-\-nv$' | wc -l) -eq 0 ] ; then
        EX_OPTIONS="${EX_OPTIONS} --nv"
        rm -rf ~/.nv || true
      fi
    else
      export CUDA_VISIBLE_DEVICES=""
    fi
    for m in $(echo "$MOUNT_POINTS" | tr ',' '\n') ; do
      x=$(echo $m | sed 's|:.*||')
      [ -e $x ] || continue
      BINDPATH="${BINDPATH},${m}"
    done
    CONTAINER_CMD="singularity"
    BINDPATH_ENV="SINGULARITY_BINDPATH"
    if which apptainer >/dev/null 2>&1 ; then
      CONTAINER_CMD="apptainer"
      BINDPATH_ENV="APPTAINER_BINDPATH"
    fi
    export ${BINDPATH_ENV}="$(echo ${BINDPATH},${ws} | sed 's|^,||')"
    ERR=0
    precmd="export ORIGINAL_${BINDPATH_ENV}=\${$BINDPATH_ENV}; export ${BINDPATH_ENV}=''; export SINGULARITY_BIND=''; export APPTAINER_BIND=''; "
    ENV_PATH="/cvmfs/cms.cern.ch"
    if which scram >/dev/null 2>&1 ; then
      ENV_PATH=$(which scram | sed 's|/common/scram$||')
    fi
    if [ -f ${ENV_PATH}/cmsset_default.sh ] ; then
      precmd="${precmd} source ${ENV_PATH}/cmsset_default.sh ;"
    fi
    if [ $(echo $HOME | grep '^/afs/' | wc -l) -gt 0 ] ; then
      if [ $(${CONTAINER_CMD} -s exec ${EX_OPTIONS} $DOCKER_IMGX sh -c 'echo $HOME' 2>&1 | grep "container creation failed: mount $HOME->" | wc -l) -gt 0 ]  ; then
        EX_OPTIONS="--no-home $EX_OPTIONS"
      fi
    fi
    PATH=$PATH:/usr/sbin ${CONTAINER_CMD} -s exec ${EX_OPTIONS} $DOCKER_IMGX sh -c "${precmd} $CMD2RUN" || ERR=$?
    if $CLEAN_UP_CACHE ; then rm -rf $SINGULARITY_CACHEDIR ; fi
    exit $ERR
  fi
else
  cd $WORKSPACE
  [ -f /cvmfs/cms.cern.ch/cmsset_default.sh ] && source /cvmfs/cms.cern.ch/cmsset_default.sh
  voms-proxy-init -voms cms -valid 24:00 || true
  eval $@
fi
