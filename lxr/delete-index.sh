#!/bin/bash -ex 
source $(dirname $0)/version_utils.sh
BASE_DIR=/data/lxr
[ "X$1" = "X" ] && exit 1
tag=$1
delete_version ${BASE_DIR}/host_config/versions ${tag}
sort_version   ${BASE_DIR}/host_config/versions
set_default    ${BASE_DIR}/host_config/versions ${BASE_DIR}/host_config/default

[ -d ${BASE_DIR}/src/$tag ] && rm -rf ${BASE_DIR}/src/$tag
[ -d ${BASE_DIR}/glimpse_index/lxr/${tag} ] && rm -rf ${BASE_DIR}/glimpse_index/lxr/${tag}

DOCKER_LXR=$(docker ps -a -q --filter 'name=lxr')
if [ "X${DOCKER_LXR}" = "X" ] ; then
  ${BASE_DIR}/scripts/run_lxr.sh
  #wait for mysql server to come up
  sleep 120
  DOCKER_LXR=$(docker ps -a -q --filter 'name=lxr')
fi
docker exec -u lxr -t lxr /lxr/host_config/cleanup-db.sh "${tag}"

