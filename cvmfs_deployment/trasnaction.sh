#!/bin/bash
CVMFS_BASE=/cvmfs/${CVMFS_REPOSITORY}
if [ "${USE_CVMFS_GW}" = "true" ] ; then
  THISDIR=$(dirname $0)
  CVMFS_PUBLISH_PATH=${CVMFS_REPOSITORY}/$(echo $1 | sed -e 's|^//*||;s|//*$||')
  GW_API=$(grep '^CVMFS_UPSTREAM_STORAGE=' /etc/cvmfs/repositories.d/${CVMFS_REPOSITORY}/server.conf | sed 's|.*,||')
  while true ; do
    cvmfs_server abort -f || true
    rm -f /var/spool/${CVMFS_BASE}/is_publishing.lock
    rm -f /var/spool/${CVMFS_BASE}/session_token
    if ! ${THISDIR}/has_lease.py ${GW_API} ${CVMFS_PUBLISH_PATH} ; then
      if cvmfs_server transaction ${CVMFS_PUBLISH_PATH} ; then break ; fi
    fi
    sleep 10
  done
else
  cvmfs_server transaction || ((cvmfs_server abort -f || rm -fR /var/spool/${CVMFS_BASE}/is_publishing.lock) && cvmfs_server transaction)
fi
