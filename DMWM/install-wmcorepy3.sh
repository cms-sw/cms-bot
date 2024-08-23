#! /bin/bash -e

# Install from git code, set paths appropriately for testing
set +x
. deploy/current/apps/wmagentpy3/etc/profile.d/init.sh
set -x

rm -rf install
python3 --version
(cd code && python3 setup.py install --prefix=../install)

echo "Sourcing wmagentpy3 and wmcorepy3-devtools init.sh scripts"
set +x
. deploy/current/apps/wmagentpy3/etc/profile.d/init.sh
# Instead of sourcing deploy/current/config/admin/init.sh, let's try wmcorepy3-devtools
. deploy/current/apps/wmcorepy3-devtools/etc/profile.d/init.sh
set -x

# these export are too verbose
set +x
export WMCORE_ROOT=$PWD/install
export PATH=$WMCORE_ROOT/install/bin:$PATH
export PYTHONPATH=$WMCORE_ROOT/lib/python3.8/site-packages:$PYTHONPATH
set -x
export PYTHONPATH=$WMCORE_ROOT/test/python:$PYTHONPATH

echo "Sourcing secrets and setting DB connectors"
set +x # don't echo secrets
. $WMAGENT_SECRETS_LOCATION
export DATABASE=mysql://${MYSQL_USER}@localhost/wmcore_unittest
export COUCHURL="http://${COUCH_USER}:${COUCH_PASS}@${COUCH_HOST}:${COUCH_PORT}"
set -x

export RUCIO_HOST=$RUCIO_HOST
export RUCIO_AUTH=$RUCIO_AUTH
