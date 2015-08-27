#!/bin/bash -ex
if [ "X$DOCKER_IMG" != X ]; then
  DOCK_ARGS="kinit cmsbuild@CERN.CH -k -t /home/cmsbuild/cmsbuild.keytab || true; cd $WORKSPACE; $@"
  echo "Passing to docker the args: "$DOCK_ARGS
  docker run -h `hostname` \
    -v /etc/localtime:/etc/localtime:ro \
    -v /build/cmsbuild:/build/cmsbuild \
    -v /home/cmsbuild:/home/cmsbuild \
    -v /afs:/afs \
    -e WORKSPACE=$WORKSPACE \
    -e BUILD_NUMBER=$BUILD_NUMBER \
    $DOCKER_IMG sh -c "$DOCK_ARGS"
else
  eval $@
fi
