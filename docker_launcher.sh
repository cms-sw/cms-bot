#!/bin/bash -ex
voms-proxy-init -valid 24:00 || true
export X509_USER_PROXY=/tmp/x509up_u`id -u`
RUN_NATIVE=
if [ "X$NOT_RUN_DOCKER" != "X" -a "X$DOCKER_IMG" != "X"  ] ; then
  RUN_NATIVE=`echo $DOCKER_IMG | grep "$NOT_RUN_DOCKER"`
fi
if [ "X$DOCKER_IMG" != X -a "X$RUN_NATIVE" = "X" ]; then
  XUSER=`whoami`
  DOCKER_OPT=""
  case $XUSER in
    cmsbld ) DOCKER_OPT=" -u 501:501 -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group " ;;
  esac
  DOCK_ARGS="kinit cmsbuild@CERN.CH -k -t /home/${XUSER}/cmsbuild.keytab || true; cd $WORKSPACE; $@"
  echo "Passing to docker the args: "$DOCK_ARGS
  docker run --rm -h `hostname` $DOCKER_OPT \
    -v $X509_USER_PROXY:$X509_USER_PROXY \
    -v /etc/localtime:/etc/localtime \
    -v /build/$XUSER:/build/$XUSER \
    -v /home/$XUSER:/home/$XUSER \
    -v /cvmfs:/cvmfs \
    -v /afs:/afs \
    -v /tmp:/tmp \
    -e WORKSPACE=$WORKSPACE \
    -e BUILD_NUMBER=$BUILD_NUMBER \
    -e X509_USER_PROXY=$X509_USER_PROXY \
    -e PYTHONPATH=/afs/cern.ch/user/c/cmsbuild/public/pygithub/lib/python2.6/site-packages \
    $DOCKER_IMG sh -c "$DOCK_ARGS"
else
  eval $@
fi
