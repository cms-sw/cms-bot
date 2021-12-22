#! /bin/bash -e

# Install from git code, set paths appropriately for testing

set +x
. deploy/current/apps/wmagent/etc/profile.d/init.sh
set -x
rm -rf install

(cd code && python setup.py install --prefix=../install)

set +x
. deploy/current/apps/wmagent/etc/profile.d/init.sh
set -x
. deploy/current/config/admin/init.sh

export WMCORE_ROOT=$PWD/install
export PATH=$WMCORE_ROOT/install/bin:$PATH
export PYTHONPATH=$WMCORE_ROOT/lib/python2.7/site-packages:$PYTHONPATH
export PYTHONPATH=$WMCORE_ROOT/test/python:$PYTHONPATH

echo "Sourcing secrets and setting DB connectors"
set +x # don't echo secrets
. $WMAGENT_SECRETS_LOCATION
export DATABASE=mysql://${MYSQL_USER}@localhost/wmcore_unittest
export COUCHURL="http://${COUCH_USER}:${COUCH_PASS}@${COUCH_HOST}:${COUCH_PORT}"
set -x

export RUCIO_HOST=$RUCIO_HOST
export RUCIO_AUTH=$RUCIO_AUTH
