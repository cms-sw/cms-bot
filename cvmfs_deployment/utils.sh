#!/bin/bash
export CVMFS_DEPLOYMENT_DIR=$(realpath $(dirname ${BASH_ARGV[0]}))
export CVMFS_BASEDIR=/cvmfs/${CVMFS_REPOSITORY}
export USE_CVMFS_GW=false
export CVMFS_GATEWAY_API=""
if grep '^CVMFS_UPSTREAM_STORAGE=gw' /etc/cvmfs/repositories.d/${CVMFS_REPOSITORY}/server.conf 2>/dev/null ; then
  export CVMFS_GATEWAY_API=$(grep '^CVMFS_UPSTREAM_STORAGE=gw' /etc/cvmfs/repositories.d/${CVMFS_REPOSITORY}/server.conf | sed 's|.*,||')
  export USE_CVMFS_GW=true
fi

function cvmfs_transaction()
{
  if ${USE_CVMFS_GW} ; then
    local lease_path=${CVMFS_REPOSITORY}/$(echo $1 | sed -e 's|^//*||;s|//*$||')
    while true ; do
      cvmfs_server abort -f || true
      ls -l /var/spool/${CVMFS_BASEDIR}/
      rm -f /var/spool/${CVMFS_BASEDIR}/is_publishing.lock
      rm -f /var/spool/${CVMFS_BASEDIR}/session_token
      rm -f /var/spool/${CVMFS_BASEDIR}/in_transaction.lock
      if ! ${CVMFS_DEPLOYMENT_DIR}/has_lease.py ${CVMFS_GATEWAY_API} ${lease_path} ; then
        if cvmfs_server transaction ${lease_path} ; then break ; fi
      fi
      sleep 10
    done
  else
    cvmfs_server transaction || ((cvmfs_server abort -f || rm -fR /var/spool/${CVMFS_BASEDIR}/is_publishing.lock) && cvmfs_server transaction)
  fi
}
