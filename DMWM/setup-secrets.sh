#! /bin/bash -e

echo "Turning off tracing to avoid revealing secrets"
set +x

start=`date +%s`

cp /build/`whoami`/secrets/dmwm-config.tmpl $WORKSPACE/wmas
perl -p -i -e "s/THISHOSTNAME/`hostname`/" $WORKSPACE/wmas
perl -p -i -e "s/srtest/dmwmtest/" $WORKSPACE/wmas
. $WORKSPACE/wmas
export WMAGENT_SECRETS_LOCATION=$WORKSPACE/wmas
export X509_HOST_CERT=$COUCH_CERT_FILE
export X509_HOST_KEY=$COUCH_KEY_FILE
export X509_USER_CERT=$COUCH_CERT_FILE
export X509_USER_KEY=$COUCH_KEY_FILE

set -x
voms-proxy-init -voms cms -out $WORKSPACE/x509up_u`id -u`
export X509_USER_PROXY=$WORKSPACE/x509up_u`id -u`

end=`date +%s`
runtime=$((end-start))

echo "Total time to setup secrets: $runtime"
