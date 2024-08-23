#!/bin/bash
PRINCIPAL=$1
USER=$(echo $PRINCIPAL |  sed 's|@.*||')
echo -n "Enter Password for $PRINCIPAL: "
stty -echo
read PASSWD
stty echo
echo ""

printf "%b" "addent -password -p $PRINCIPAL -k 1 -e rc4-hmac\n$PASSWD\naddent -password -p $PRINCIPAL -k 1 -e aes256-cts\n$PASSWD\nwkt ${USER}.keytab" | ktutil
klist -k ${USER}.keytab
