#!/bin/bash -ex
for cvmfs_dir in $(grep CVMFS_REPOSITORIES= /etc/cvmfs/default.local | sed "s|.*=||;s|'||g" | sed 's|"||g' | tr ',' '\n'  | grep cern.ch) ; do
  ls -l /cvmfs/${cvmfs_dir} >/dev/null 2>&1 || true
done
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
  docker run --rm -h `hostname -f` $DOCKER_OPT \
    -v /etc/localtime:/etc/localtime \
    -v /build/$XUSER:/build/$XUSER \
    -v /home/$XUSER:/home/$XUSER \
    -v /cvmfs:/cvmfs \
    -v /cvmfs/grid.cern.ch/etc/grid-security/vomses:/etc/vomses \
    -v /cvmfs/grid.cern.ch/etc/grid-security:/etc/grid-security \
    -v /tmp:/tmp \
    -v /etc/tnsnames.ora:/etc/tnsnames.ora \
    -e WORKSPACE=$WORKSPACE \
    -e USER=$USER \
    -e BUILD_NUMBER=$BUILD_NUMBER \
    -e JOB_NAME=$JOB_NAME \
    $DOCKER_IMG sh -c "$DOCK_ARGS"
else
  voms-proxy-init -voms cms -valid 24:00 || true
  eval $@
fi
