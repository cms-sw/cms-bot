function dockerrun()
{
  if [ -z "${CONTAINER_TYPE}" ] ; then
    CONTAINER_TYPE=docker
    DOCKER_IMG_BASE="/cvmfs/unpacked.cern.ch/registry.hub.docker.com"
    [ "$USE_SINGULARITY" = "true" ] && CONTAINER_TYPE=singularity
    if [ -z "${IMAGE_BASE}" ] ; then IMAGE_BASE="${DOCKER_IMG_BASE}" ; fi
    if [ -z "${PROOTDIR}" ]   ; then PROOTDIR="/cvmfs/cms-ib.cern.ch/proot" ; fi
    if [ -z "${THISDIR}" ]    ; then THISDIR=$(/bin/pwd -P) ; fi
    if [ -z "${WORKDIR}" ]    ; then WORKDIR=$(/bin/pwd -P) ; fi
    arch=$(echo $SCRAM_ARCH | cut -d_ -f2 | sed 's|amd64|x86_64|')
    os=$(echo $SCRAM_ARCH | cut -d_ -f1 | sed 's|^[a-z]*|el|')
    IMG="cmssw/${os}:${arch}"
    if [ $(uname -m) != "${arch}" ] ; then
      CONTAINER_TYPE="qemu"
      QEMU_ARGS="$PROOTDIR/latest/qemu-${arch}"
      if [ "${arch}" = "aarch64" ] ; then
        QEMU_ARGS="${QEMU_ARGS} -cpu cortex-a57"
      elif [ "${arch}" = "ppc64le" ] ; then
        QEMU_ARGS="${QEMU_ARGS} -cpu POWER8"
      fi
    fi
  fi
  case $CONTAINER_TYPE in
    docker)
      docker pull ${IMG}
      CMD_ARG="run --net=host -u $(id -u):$(id -g) --rm -t"
      CMD_ARG="${CMD_ARG} -v ${THISDIR}:${THISDIR} -v /tmp:/tmp -v /cvmfs:/cvmfs -v ${WORKDIR}:${WORKDIR}"
      if [ "${MOUNT_DIRS}" != "" ] ; then for p in ${MOUNT_DIRS} ; do CMD_ARG="${CMD_ARG} -v $p"; done ; fi
      ARGS="cd $THISDIR; for o in n s u ; do val=\"-\$o \$(ulimit -H -\$o) \${val}\"; done; ulimit \${val}; ulimit -n -s -u >/dev/null 2>&1; $@"
      docker ${CMD_ARG} ${IMG} sh -c "$ARGS"
      ;;
    singularity)
      UNPACK_IMG="${IMAGE_BASE}/${IMG}"
      CMD_ARG="-s exec -B /tmp -B /cvmfs -B ${THISDIR}:${THISDIR} -B ${WORKDIR}:${WORKDIR}"
      if [ "${MOUNT_DIRS}" != "" ] ; then for p in ${MOUNT_DIRS} ; do CMD_ARG="${CMD_ARG} -B $p"; done ; fi
      ARGS="cd $THISDIR; for o in n s u ; do val=\"-\$o \$(ulimit -H -\$o) \${val}\"; done; ulimit \${val}; ulimit -n -s -u >/dev/null 2>&1; $@"
      PATH=$PATH:/usr/sbin singularity ${CMD_ARG} ${UNPACK_IMG} sh -c "$ARGS"
      ;;
    qemu)
      ls ${IMAGE_BASE} >/dev/null 2>&1
      CMD_ARG="-b /tmp:/tmp -b /cvmfs:/cvmfs -w ${THISDIR}"
      if [ -d /build ] ; then CMD_ARG="-b /build:/build ${CMD_ARG}"; fi
      if [ "${MOUNT_DIRS}" != "" ] ; then for p in ${MOUNT_DIRS} ; do CMD_ARG="${CMD_ARG} -b $p"; done ; fi
      ARGS="cd ${THISDIR}; $@"
      $PROOTDIR/proot -R ${IMAGE_BASE}/${IMG} ${CMD_ARG} -q "${QEMU_ARGS}" sh -c "${ARGS}"
      ;;
    *) eval $@;;
  esac
}
