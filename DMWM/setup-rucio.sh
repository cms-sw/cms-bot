#! /bin/bash -e

echo "AMR Updating the rucio.cfg file used by WMCore Jenkins"

sed -i "s+RUCIO_HOST_OVERWRITE+$RUCIO_HOST+" $RUCIO_HOME/etc/rucio.cfg
sed -i "s+RUCIO_AUTH_OVERWRITE+$RUCIO_AUTH+" $RUCIO_HOME/etc/rucio.cfg
sed -i "s+\$X509_USER_CERT+$X509_USER_CERT+" $RUCIO_HOME/etc/rucio.cfg
sed -i "s+\$X509_USER_KEY+$X509_USER_KEY+" $RUCIO_HOME/etc/rucio.cfg
sed -i "s+\$X509_USER_PROXY+$X509_USER_PROXY+" $RUCIO_HOME/etc/rucio.cfg

echo "Done updating rucio.cfg file"
