#!/bin/bash -ex
cvmfs_config probe
RUN_NATIVE=
if [ "X$DOCKER_IMG" = "X" -a "$DOCKER_IMG_HOST" != "X" ] ; then DOCKER_IMG=$DOCKER_IMG_HOST ; fi
if [ "X$NOT_RUN_DOCKER" != "X" -a "X$DOCKER_IMG" != "X"  ] ; then
  RUN_NATIVE=`echo $DOCKER_IMG | grep "$NOT_RUN_DOCKER"`
fi
if [ "X$DOCKER_IMG" != X -a "X$RUN_NATIVE" = "X" ]; then
  docker pull $DOCKER_IMG
  XUSER=`whoami`
  DOCKER_OPT=""
  case $XUSER in
    cmsbld ) DOCKER_OPT=" -u $(id -u):$(id -g) -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group " ;;
  esac
  DOCK_ARGS="voms-proxy-init -voms cms -valid 24:00|| true ; cd $WORKSPACE; $@"
  echo "Passing to docker the args: "$DOCK_ARGS
  docker run --rm -h `hostname` $DOCKER_OPT \
    -v /etc/localtime:/etc/localtime \
    -v /build/$XUSER:/build/$XUSER \
    -v /home/$XUSER:/home/$XUSER \
    -v /cvmfs:/cvmfs \
    -v /cvmfs/grid.cern.ch/etc/grid-security/vomses:/etc/vomses \
    -v /cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security \
    -v /tmp:/tmp \
    -e WORKSPACE=$WORKSPACE \
    -e BUILD_NUMBER=$BUILD_NUMBER \
    $DOCKER_IMG sh -c "$DOCK_ARGS"
else
  voms-proxy-init -voms cms -valid 24:00 || true
  eval $@
fi
