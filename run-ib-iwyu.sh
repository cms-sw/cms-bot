#!/bin/bash -ex
P=$(readlink -f $0)
DIR_NAME=$(dirname $P)
RELEASE_NAME=$1
ARCHITECTURE=$2
echo 'Running Scram'
scram -a $ARCHITECTURE project $RELEASE_NAME
cd $RELEASE_NAME
eval `scram run -sh`
cp -R $CMSSW_RELEASE_BASE/src/* src 
find src/ -maxdepth 2 -type l -exec rm -f {} \;
CPUS=`nproc`
if [ `hostname | grep '^lxplus' | wc -l` = '1' ]
  let CPUS=$CPUS/2
fi
BUILD_LOG=yes scram b -k -j $CPUS compile COMPILER=iwyu
scram build -f buildlog
rm -rf iwyu/
mkdir iwyu
for logfile in `find tmp/$ARCHITECTURE/cache/log/src -name 'build.log' -type f` ; do
  DIR=`echo $logfile | cut -d/ -f6,7`
  mkdir -p iwyu/$DIR
  $DIR_NAME/parse_iwyu_logs.py $logfile $RELEASE_NAME >iwyu/$DIR/index.html 
  cp $logfile iwyu/$DIR
done
