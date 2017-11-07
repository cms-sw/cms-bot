#!/bin/bash -ex 
BASE_DIR=/data/lxr
[ "X$1" = "X" ] && exit 1
tag=$1
if [ $(grep "^$tag$" ${BASE_DIR}/host_config/versions | wc -l) -gt 0 ] ; then
  grep    '_X_' ${BASE_DIR}/host_config/versions | grep -v "^$tag$" | sort | uniq | tac  > ${BASE_DIR}/host_config/versions.new
  grep -v '_X_' ${BASE_DIR}/host_config/versions | grep -v "^$tag$" | sort | uniq | tac >> ${BASE_DIR}/host_config/versions.new
  mv ${BASE_DIR}/host_config/versions.new ${BASE_DIR}/host_config/versions
fi
head -1 ${BASE_DIR}/host_config/versions > ${BASE_DIR}/host_config/default

[ -d ${BASE_DIR}/src/$tag ] && rm -rf /data/lxr/src/$tag
[ -d ${BASE_DIR}/glimpse_index/lxr/${tag} ] && rm -rf ${BASE_DIR}/glimpse_index/lxr/${tag}

DOCKER_LXR=$(docker ps -a -q --filter 'name=lxr')
if [ "X${DOCKER_LXR}" = "X" ] ; then
  ${BASE_DIR}/scripts/run_lxr.sh
  #wait for mysql server to come up
  sleep 120
  DOCKER_LXR=$(docker ps -a -q --filter 'name=lxr')
fi
docker exec -u lxr -t lxr /lxr/host_config/cleanup-db.sh "${tag}"

