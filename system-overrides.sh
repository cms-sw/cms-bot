#!/bin/bash -x
#This script generate system commands which hangs under ASAN/UBSAN env
#Idea is to unset LD_PRELOAD and then call the actual system command
OVERRIDE_DIR=$1
[ "$1" != "" ] || OVERRIDE_DIR=$(/bin/pwd -P)
mkdir -p ${OVERRIDE_DIR}
for cmd in ps ; do
  if [ ! -x ${OVERRIDE_DIR}/${cmd} ] ; then
    sys_cmd=$(which $cmd || echo "")
    echo '#!/bin/bash' > ${OVERRIDE_DIR}/${cmd}
    echo "LD_PRELOAD='' exec ${sys_cmd} \"\$@\"" >> ${OVERRIDE_DIR}/${cmd}
    chmod +x ${OVERRIDE_DIR}/${cmd}
  fi
done
