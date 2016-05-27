#!/bin/bash -ex
P=$(readlink -f $0)
DIR_NAME=$(dirname $P)
RELEASE_NAME=$1
ARCHITECTURE=$2
echo 'Running Scram'
scram -a $ARCHITECTURE project $RELEASE_NAME
cd $RELEASE_NAME
eval `scram run -sh`
rm -rf src
cp -r $CMSSW_RELEASE_BASE/src src
find src -maxdepth 2 -type l -exec rm -f {} \;
CPUS=`nproc`
if [ `hostname | grep '^lxplus' | wc -l` = '1' ]; then
  let CPUS=$CPUS/2
fi
<<<<<<< HEAD
BUILD_LOG=yes scram b -k -j $CPUS compile COMPILER=iwyu | true
scram build -f buildlog
rm -rf iwyu/
mkdir iwyu
if [ -d "tmp/$ARCHITECTURE/cache/log/src" ] ; then
 for logfile in `find tmp/$ARCHITECTURE/cache/log/src -name 'build.log' -type f` ; do
   DIR=`echo $logfile | cut -d/ -f6,7`
   mkdir -p iwyu/$DIR
   $DIR_NAME/parse_iwyu_logs.py $logfile $RELEASE_NAME >iwyu/$DIR/index.html 
   cp $logfile iwyu/$DIR
 done
else
exit 0
=======
BUILD_LOG=yes scram b -k -j $CPUS compile COMPILER=iwyu || true
scram build -f buildlog
if [ -d tmp/$ARCHITECTURE/cache/log/src ] ; then
  for logfile in `find tmp/$ARCHITECTURE/cache/log/src -name 'build.log' -type f` ; do
    DIR=`echo $logfile | cut -d/ -f6,7`
    mkdir -p iwyu/$DIR
    $DIR_NAME/parse_iwyu_logs.py $logfile $RELEASE_NAME >iwyu/$DIR/index.html
    cp $logfile iwyu/$DIR
  done
>>>>>>> aaa2512417e5949b3e9d91c13665f50ca371513d
fi
