#!/bin/bash -ex

PROOT_URL="https://cmssdt.cern.ch/SDT/proot/"
#PROOTDIR=$1

if [[ ! -d $HOST_PROOT_DIR ]] ; then
    mkdir -p $HOST_PROOT_DIR
    cd $HOST_PROOT_DIR
    wget -nv -r -nH -nd -np -m -R *.html* $PROOT_URL
    #  make proot and care executable
    chmod +x ${HOST_PROOT_DIR}/care ${HOST_PROOT_DIR}/proot  ${HOST_PROOT_DIR}/qemu*
    for i in `ls | grep bz2`; do
	tar xjf $i ;
	done
fi
