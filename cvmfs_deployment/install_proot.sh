#!/bin/bash -ex

PROOT_URL="https://cmssdt.cern.ch/SDT/proot/"
#PROOTDIR=$1

if [[ ! -d $PROOT_DIR ]] ; then
    mkdir -p $PROOT_DIR
    cd $PROOT_DIR
    wget -nv -r -nH -nd -np -m -R *.html* $PROOT_URL
    #  make proot and care executable
    chmod +x ${PROOT_DIR}/care ${PROOT_DIR}/proot  ${PROOT_DIR}/qemu*
    for i in `ls | grep bz2`; do
	tar xjf $i ;
	done
fi
