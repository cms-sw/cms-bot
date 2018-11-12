dockerrun()
{
  SCRAM_ARCH=$ARCHITECTURE
  case $SCRAM_ARCH in
    slc6_amd64_* )
      ARGS="cd ${INSTALL_PATH}; $@"
      docker run --net=host --rm -t -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group -e INSTALL_PATH=${INSTALL_PATH} -e SCRAM_ARCH=${SCRAM_ARCH} -e x=${x} -v /tmp:/tmp -v ${INSTALL_PATH}:${INSTALL_PATH} -u $(whoami) cmssw/slc6-installer:latest sh -c "${ARGS}"
      ;;
    slc7_amd64_* )
      ARGS="cd ${INSTALL_PATH}; $@"
      docker run --net=host --rm -t -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group -e INSTALL_PATH=${INSTALL_PATH} -e SCRAM_ARCH=${SCRAM_ARCH} -e x=${x} -v /tmp:/tmp -v ${INSTALL_PATH}:${INSTALL_PATH} -u $(whoami) cmssw/slc7-installer:latest sh -c "${ARGS}"
      ;;
    slc7_aarch64_* )
      ARGS="export INSTALL_PATH=${INSTALL_PATH}; export INSTALL_PATH=${INSTALL_PATH}; export SCRAM_ARCH=${SCRAM_ARCH}; export x=${x}; cd ${INSTALL_PATH}; $@"
      $PROOT_DIR/proot -R $PROOT_DIR/centos-7.2.1511-aarch64-rootfs -b /tmp:tmp -b /build:/build -b /cvmfs:/cvmfs -w ${INSTALL_PATH} -q "$PROOT_DIR/qemu-aarch64 -cpu cortex-a57" sh -c "${ARGS}"
      ;;
    fc24_ppc64le_* )
      ARGS="export INSTALL_PATH=${INSTALL_PATH}; export INSTALL_PATH=${INSTALL_PATH}; export SCRAM_ARCH=${SCRAM_ARCH}; export x=${x}; cd ${INSTALL_PATH}; $@"
      $PROOT_DIR/proot -R $PROOT_DIR/fedora-24-ppc64le-rootfs -b /tmp:/tmp -b /build:/build -b /cvmfs:/cvmfs -w ${INSTALL_PATH} -q "$PROOT_DIR/qemu-ppc64le -cpu POWER8" sh -c "${ARGS}"
      ;;
    slc7_ppc64le_* )
      ARGS="export INSTALL_PATH=${INSTALL_PATH}; export INSTALL_PATH=${INSTALL_PATH}; export SCRAM_ARCH=${SCRAM_ARCH}; export x=${x}; cd ${INSTALL_PATH}; $@"
      $PROOT_DIR/proot -R $PROOT_DIR/centos-7.2.1511-ppc64le-rootfs -b /tmp:/tmp -b /build:/build -b /cvmfs:/cvmfs -w ${INSTALL_PATH} -q "$PROOT_DIR/qemu-ppc64le -cpu POWER8" sh -c "${ARGS}"
      ;;
    * )
      eval $@
      ;;
  esac
}
