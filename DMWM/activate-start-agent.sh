#! /bin/bash -e

rm -rf $DBSOCK || true
echo "Attempting to activate agent"
if [[ -d $PWD/deploy/current/config/wmagentpy3 ]]
then
    $PWD/deploy/current/config/wmagentpy3/manage activate-agent
else
    $PWD/deploy/current/config/wmagent/manage activate-agent
fi
unlink deploy/current/sw*/var || /bin/true

echo "Starting services"
if [[ -d $PWD/deploy/current/config/wmagentpy3 ]]
then
    $PWD/deploy/current/config/wmagentpy3/manage start-services
else
    $PWD/deploy/current/config/wmagent/manage start-services
fi
