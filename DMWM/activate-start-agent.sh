#! /bin/bash -e

rm -rf $DBSOCK || true
echo "Attempting to activate agent"
$PWD/deploy/current/config/wmagent/manage activate-agent
unlink deploy/current/sw*/var || /bin/true
echo "Starting services"
$PWD/deploy/current/config/wmagent/manage start-services
