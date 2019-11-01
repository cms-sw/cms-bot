#!/bin/bash -ex
kinit -R || true
ulimit -a || true
for repo in cms cms-ib grid projects unpacked ; do
  ls -l /cvmfs/${repo}.cern.ch >/dev/null 2>&1 || true
done
RUN_NATIVE=
if [ "X$DOCKER_IMG" = "X" -a "$DOCKER_IMG_HOST" != "X" ] ; then DOCKER_IMG=$DOCKER_IMG_HOST ; fi
if [ "X$NOT_RUN_DOCKER" != "X" -a "X$DOCKER_IMG" != "X"  ] ; then
  RUN_NATIVE=`echo $DOCKER_IMG | grep "$NOT_RUN_DOCKER"`
fi
if [ "X$DOCKER_IMG" != X -a "X$RUN_NATIVE" = "X" ]; then
  if [ "X$WORKSPACE" = "X" ] ; then export WORKSPACE=$(/bin/pwd) ; fi
  BUILD_BASEDIR=$(dirname $WORKSPACE)
  export KRB5CCNAME=$(klist | grep 'Ticket cache: FILE:' | sed 's|.* ||')
  MOUNT_POINTS="/cvmfs,/tmp"
  for xdir in /cvmfs/grid.cern.ch/etc/grid-security/vomses:/etc/vomses /cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security ; do
    ldir=$(echo $xdir | sed 's|.*:||')
    if [ $(echo "${IGNORE_MOUNTS}" | tr ' ' '\n' | grep "^${ldir}$" | wc -l) -gt 0 ] ; then
      continue
    fi
    if [ -d $ldir -a $(ls $ldir |wc -l) -gt 0 ] ; then xdir=$ldir; fi
    MOUNT_POINTS="$MOUNT_POINTS,${xdir}"
  done
  if [ $(echo $HOME |  grep '^/home/' | wc -l)  -gt 0 ] ; then
    MOUNT_POINTS="$MOUNT_POINTS,/home"
  fi
  if [ -d /afs/cern.ch ] ; then MOUNT_POINTS="${MOUNT_POINTS},/afs"; fi
  if [ "$(uname -m)" = "x86_64" ] ; then
    if [ -e /etc/tnsnames.ora ] ; then MOUNT_POINTS="${MOUNT_POINTS},/etc/tnsnames.ora" ; fi
  fi
  HAS_DOCKER=false
  if [ "X$USE_SINGULARITY" != "Xtrue" ] ; then
    if [ $(id -Gn 2>/dev/null | grep docker | wc -l) -gt 0 ] ; then
      HAS_DOCKER=$(docker --version >/dev/null 2>&1 && echo true || echo false)
    fi
  fi
  CMD2RUN=""
  XUSER=`whoami`
  if [ -d $HOME/bin ] ; then
    if [ $(echo $PATH | tr ':' '\n' | grep $HOME/bin | wc -l) -eq 0 ] ; then
      CMD2RUN="export PATH=$HOME/bin:$PATH; "
    fi
  fi
  CMD2RUN="${CMD2RUN}voms-proxy-init -voms cms -valid 24:00|| true ; cd $WORKSPACE; $@"
  if $HAS_DOCKER ; then
    docker pull $DOCKER_IMG
    set +x
    DOCKER_OPT="-e USER=$XUSER"
    case $XUSER in
      cmsbld ) DOCKER_OPT="${DOCKER_OPT} -u $(id -u):$(id -g) -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group" ;;
    esac
    for e in $DOCKER_JOB_ENV WORKSPACE BUILD_NUMBER JOB_NAME DOCKER_IMG; do DOCKER_OPT="${DOCKER_OPT} -e $e"; done
    for m in $(echo $MOUNT_POINTS,/etc/localtime,${BUILD_BASEDIR},/home/$XUSER | tr ',' '\n') ; do
      if [ $(echo $m | grep ':' | wc -l) -eq 0 ] ; then m="$m:$m";fi
      DOCKER_OPT="${DOCKER_OPT} -v $m"
    done
    if [ "X$KRB5CCNAME" != "X" ] ; then DOCKER_OPT="${DOCKER_OPT} -e KRB5CCNAME=$KRB5CCNAME" ; fi
    set -x
    echo "Passing to docker the args: "$CMD2RUN
    docker run --rm --net=host $DOCKER_OPT $DOCKER_IMG sh -c "$CMD2RUN"
  else
    ws=$(echo $WORKSPACE |  cut -d/ -f1-2)
    CLEAN_UP_CACHE=false
    DOCKER_IMGX=""
    if [ -e /cvmfs/unpacked.cern.ch/registry.hub.docker.com/$DOCKER_IMG ] ; then
      DOCKER_IMGX=/cvmfs/unpacked.cern.ch/registry.hub.docker.com/$DOCKER_IMG
    elif [ -e /cvmfs/cms-ib.cern.ch/docker/$DOCKER_IMG ] ; then
      DOCKER_IMGX=/cvmfs/cms-ib.cern.ch/docker/$DOCKER_IMG
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
    fi
    if [ "X$TEST_CONTEXT" = "XGPU" -o -e "/proc/driver/nvidia/version" ] ; then
      if [ $(echo "${SINGULARITY_OPTIONS}" | tr ' ' '\n' | grep '^\-\-nv$' | wc -l) -eq 0 ] ; then
        SINGULARITY_OPTIONS="${SINGULARITY_OPTIONS} --nv"
      fi
    fi
    export SINGULARITY_BINDPATH="${MOUNT_POINTS},$ws"
    if [ $(whoami) = "cmsbuild" -a $(echo $HOME | grep /afs/ | wc -l) -gt 0 ] ; then
      SINGULARITY_OPTIONS="${SINGULARITY_OPTIONS} -B $HOME:/home/cmsbuild"
    fi
    ERR=0
    singularity exec $SINGULARITY_OPTIONS $DOCKER_IMGX sh -c "source /cvmfs/cms.cern.ch/cmsset_default.sh ; $CMD2RUN" || ERR=$?
    if $CLEAN_UP_CACHE ; then rm -rf $SINGULARITY_CACHEDIR ; fi
    exit $ERR
  fi
else
  voms-proxy-init -voms cms -valid 24:00 || true
  eval $@
fi
