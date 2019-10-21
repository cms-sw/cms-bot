function dockerrun()
{
  CONTAINER_TYPE=docker
  if [ "$USE_SINGULARITY" = "true" ] ; then CONTAINER_TYPE=singularity ; fi
  case "$SCRAM_ARCH" in
    slc6_amd64_* ) IMG="cmssw/slc6:latest" ;;
    slc7_amd64_* ) IMG="cmssw/cc7:latest" ;;
    cc8_amd64_* ) IMG="cmssw/cc8:latest" ;;
    slc7_aarch64_* )
      CONTAINER_TYPE="qemu"
      IMG="cmssw/cc7-aarch64:latest"
      QEMU_ARGS="$PROOTDIR/qemu-aarch64 -cpu cortex-a57"
      ;;
    slc7_ppc64le_* )
      CONTAINER_TYPE="qemu"
      IMG="cmssw/cc7-ppc64le:latest"
      QEMU_ARGS="$PROOTDIR/qemu-ppc64le -cpu POWER8"
      ;;
    * )
      CONTAINER_TYPE="host"
      ;;
  esac
  SIN_MOUNT=$(echo $THISDIR | cut -d/ -f1,2)
  case $CONTAINER_TYPE in
    docker)
      docker pull ${IMG}
      DOC_ARG="run --net=host -u $(id -u):$(id -g) --rm -t"
      DOC_ARG="${DOC_ARG} -e THISDIR=${THISDIR} -e WORKDIR=${WORKDIR}"
      DOC_ARG="${DOC_ARG} -e TMPDIR=${TMPDIR} -e SCRAM_ARCH=${SCRAM_ARCH} -e x=${x}"
      DOC_ARG="${DOC_ARG} -v $SIN_MOUNT:$SIN_MOUNT:Z"
      ARGS="cd $THISDIR; for o in n s u ; do val=\"-\$o \$(ulimit -H -\$o) \${val}\"; done; ulimit \${val}; $@"
      docker $DOC_ARG ${IMG} sh -c "$ARGS"
      ;;
    singularity)
      ls /cvmfs/cms-ib.cern.ch >/dev/null 2>&1
      ls /cvmfs/unpacked.cern.ch >/dev/null 2>&1
      UNPACK_IMG="/cvmfs/unpacked.cern.ch/registry.hub.docker.com/${IMG}"
      if [ ! -e ${UNPACK_IMG} ] ; then
        UNPACK_IMG="/cvmfs/cms-ib.cern.ch/docker/${IMG}"
      fi
      ARGS="cd $THISDIR; for o in n s u ; do val=\"-\$o \$(ulimit -H -\$o) \${val}\"; done; ulimit \${val}; $@"
      singularity -s exec -B /cvmfs -B $SIN_MOUNT:$SIN_MOUNT ${UNPACK_IMG} sh -c "$ARGS"
      ;;
    qemu)
      ls /cvmfs/cms-ib.cern.ch >/dev/null 2>&1
      ARGS="export THISDIR=${THISDIR}; export WORKDIR=${WORKDIR}; export SCRAM_ARCH=${SCRAM_ARCH}; export x=${x}; cd ${THISDIR}; $@"
      $PROOTDIR/proot -R /cvmfs/cms-ib.cern.ch/docker/${IMG} -b /tmp:tmp -b /build:/build -b /cvmfs:/cvmfs -w ${THISDIR} -q "${QEMU_ARGS}" sh -c "$ARGS"
      ;;
    host) eval $@;;
  esac
}
