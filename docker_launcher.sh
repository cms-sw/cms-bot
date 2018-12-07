#!/bin/bash -ex
kinit -R || true
for repo in cms cms-ib grid projects ; do
  ls -l /cvmfs/${repo}.cern.ch >/dev/null 2>&1 || true
done
RUN_NATIVE=
if [ "X$DOCKER_IMG" = "X" -a "$DOCKER_IMG_HOST" != "X" ] ; then DOCKER_IMG=$DOCKER_IMG_HOST ; fi
if [ "X$NOT_RUN_DOCKER" != "X" -a "X$DOCKER_IMG" != "X"  ] ; then
  RUN_NATIVE=`echo $DOCKER_IMG | grep "$NOT_RUN_DOCKER"`
fi
if [ "X$DOCKER_IMG" != X -a "X$RUN_NATIVE" = "X" ]; then
  if [ "X$WORKSPACE" = "X" ] ; then export WORKSPACE=$(/bin/pwd) ; fi
  BUILD_BASEDIR=$(echo $WORKSPACE |  cut -d/ -f1-3)
  export KRB5CCNAME=$(klist | grep 'Ticket cache: FILE:' | sed 's|.* ||')
  MOUNT_POINTS="/cvmfs,/tmp,/cvmfs/grid.cern.ch/etc/grid-security/vomses:/etc/vomses,/cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security"
  if [ -e /etc/tnsnames.ora ] ; then MOUNT_POINTS="${MOUNT_POINTS},/etc/tnsnames.ora" ; fi
  HAS_DOCKER=$(docker version >/dev/null 2>&1 && echo true || echo false)
  CMD2RUN="voms-proxy-init -voms cms -valid 24:00|| true ; cd $WORKSPACE; $@"
  XUSER=`whoami`
  if $HAS_DOCKER ; then
    docker pull $DOCKER_IMG
    DOCKER_OPT="-e USER=$XUSER"
    case $XUSER in
      cmsbld ) DOCKER_OPT="${DOCKER_OPT} -u $(id -u):$(id -g) -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group" ;;
    esac
    for e in $DOCKER_JOB_ENV WORKSPACE BUILD_NUMBER JOB_NAME; do DOCKER_OPT="${DOCKER_OPT} -e $e=$(eval echo \$$e)"; done
    for m in $(echo $MOUNT_POINTS,/etc/localtime,${BUILD_BASEDIR},/home/$XUSER | tr ',' '\n') ; do
      if [ $(echo $m | grep ':' | wc -l) -eq 0 ] ; then m="$m:$m";fi
      DOCKER_OPT="${DOCKER_OPT} -v $m"
    done
    if [ "X$KRB5CCNAME" != "X" ] ; then DOCKER_OPT="${DOCKER_OPT} -e KRB5CCNAME=$KRB5CCNAME" ; fi
    echo "Passing to docker the args: "$CMD2RUN
    docker run --rm -h `hostname -f` $DOCKER_OPT $DOCKER_IMG sh -c "$CMD2RUN"
  else
    export SINGULARITY_CACHEDIR="${BUILD_BASEDIR}/singularity"
    export SINGULARITY_BINDPATH=${MOUNT_POINTS}
    singularity exec docker://$DOCKER_IMG sh -c "$CMD2RUN"
  fi
else
  voms-proxy-init -voms cms -valid 24:00 || true
  eval $@
fi
