#!/bin/bash -e
cat <<EOF
#!/bin/bash -ex
XDIR=\$(/bin/pwd)
export SCRAM_ARCH=${ARCHITECTURE}
if [ -e '${RELEASE_FORMAT}' ] ; then echo 'There is already ${RELEASE_FORMAT} dev area. Please cleanup or run \$0 in a clean directory' ; fi
tar -xzf ${CVMFS_DIR}/cmssw.tar.gz
cd ${RELEASE_FORMAT}
SCRAM_VER=\$(cat config/scram_version)
EXT=pl
SCRAM_HOME_BASE=src
if [ \$(echo \${SCRAM_VER} | grep '^V3' | wc -l) -gt 0 ] ; then EXT=py ; SCRAM_HOME_BASE=''; fi
EOF
if [ "${PR_REPOSITORY}" != "" ] ; then
  EXT_DIR="/cvmfs/${CVMFS_REPOSITORY}/${WEEK}/${PR_REPOSITORY}"
  if [ ! -d ${EXT_DIR}/${ARCHITECTURE}/cms/cmssw-tool-conf ] ; then
    EXT_DIR="/cvmfs/cms-ib.cern.ch/${WEEK}"
  fi
  echo "export SCRAM_TOOL_HOME=${EXT_DIR}/${ARCHITECTURE}/lcg/SCRAMV1/\${SCRAM_VER}/\${SCRAM_HOME_BASE}"
  echo "./config/SCRAM/projectAreaRename.\${EXT} ${PR_BUILD_BASE}/testBuildDir ${EXT_DIR} ${ARCHITECTURE}"
else
  echo "export SCRAM_TOOL_HOME=/cvmfs/cms-ib.cern.ch/${WEEK}/share/lcg/SCRAMV1/\${SCRAM_VER}/\${SCRAM_HOME_BASE}"
fi
cat <<EOF
./config/SCRAM/projectAreaRename.\${EXT} ${PR_BUILD_BASE} \${XDIR} ${ARCHITECTURE}
set +x
if [ "${EXT_DIR}" != "" ] ; then
  echo "Relocating external/${ARCHITECTURE} symlinks"
  for L in \$(find external/${ARCHITECTURE} -type l); do
    lnk=\$(readlink -n \$L 2>&1)
    case \$lnk in
       ${PR_BUILD_BASE}/testBuildDir/*)
         al=\$(echo \$lnk | sed -e 's|${PR_BUILD_BASE}/testBuildDir/|${EXT_DIR}/|')
         rm -f \$L
         ln -sf  \$al \$L
         ;;
     esac
  done
fi
echo "Deleting generated python caches in config/SCRAM"
find config/SCRAM -name __pycache__ -type d | xargs --no-run-if-empty rm -rf
echo "Updating tools"
if [ -d .SCRAM/${ARCHITECTURE}/timestamps ] ; then
  touch .SCRAM/${ARCHITECTURE}/timestamps/*
else
  touch .SCRAM/${ARCHITECTURE}/tools/*
fi
set -x
EOF
