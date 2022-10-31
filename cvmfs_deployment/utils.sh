#!/bin/bash
export CVMFS_BASEDIR=/cvmfs/${CVMFS_REPOSITORY}
export USE_CVMFS_GW=false
if grep '^CVMFS_UPSTREAM_STORAGE=gw' /etc/cvmfs/repositories.d/${CVMFS_REPOSITORY}/server.conf 2>/dev/null ; then export USE_CVMFS_GW=true ; fi

function cvmfs_transaction()
{
  if ${USE_CVMFS_GW} ; then
    local tdir=$(dirname $0)
    local lease_path=${CVMFS_REPOSITORY}/$(echo $1 | sed -e 's|^//*||;s|//*$||')
    local gw_api=$(grep '^CVMFS_UPSTREAM_STORAGE=' /etc/cvmfs/repositories.d/${CVMFS_REPOSITORY}/server.conf | sed 's|.*,||')
    set -x
    echo "Running: cvmfs_server transaction ${lease_path}"
    while true ; do
      cvmfs_server abort -f || true
      rm -f /var/spool/${CVMFS_BASEDIR}/is_publishing.lock
      rm -f /var/spool/${CVMFS_BASEDIR}/session_token
      if ! ${tdir}/has_lease.py ${gw_api} ${lease_path} ; then
        if cvmfs_server transaction ${lease_path} ; then break ; fi
      fi
      sleep 10
    done
    set +x
  else
    cvmfs_server transaction || ((cvmfs_server abort -f || rm -fR /var/spool/${CVMFS_BASEDIR}/is_publishing.lock) && cvmfs_server transaction)
  fi
}
