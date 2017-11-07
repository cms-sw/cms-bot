#!/bin/bash -e 
BASE_DIR=/data/lxr
[ "X$1" = "X" ] && exit 1
tag=$1
DOCKER_LXR=$(docker ps -a -q --filter 'name=lxr')
if [ "X${DOCKER_LXR}" = "X" ] ; then
  ${BASE_DIR}/scripts/run_lxr.sh
  #wait for mysql server to come up
  sleep 120
  DOCKER_LXR=$(docker ps -a -q --filter 'name=lxr')
fi
rm -rf ${BASE_DIR}/glimpse_index/lxr/${tag} || true
mkdir -p ${BASE_DIR}/glimpse_index/lxr/${tag}
echo $tag >> ${BASE_DIR}/host_config/versions
grep    '_X_' ${BASE_DIR}/host_config/versions | sort | uniq | tac  > ${BASE_DIR}/host_config/versions.new
grep -v '_X_' ${BASE_DIR}/host_config/versions | sort | uniq | tac >> ${BASE_DIR}/host_config/versions.new
mv ${BASE_DIR}/host_config/versions.new ${BASE_DIR}/host_config/versions
docker exec -u lxr -t lxr /lxr/genxref --url=//localhost/lxr --version=$tag
head -1 ${BASE_DIR}/host_config/versions > ${BASE_DIR}/host_config/default
