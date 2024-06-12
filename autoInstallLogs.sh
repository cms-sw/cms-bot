#!/bin/sh -e

function ExtractLogs ()
{
  pushd $1
    if [ -f html-logs.zip ] ; then
        [ -f logAnalysis.pkl ] || (unzip -p html-logs.zip logAnalysis.pkl > logAnalysis.pkl || echo "Unable to unpack logs in $1.")
        [ -f index.html ] || (unzip -p html-logs.zip index.html >  index.html || echo "Unable to unpack logs in $1.")
    fi
  popd
}

while [ ! X$# = X0 ]; do
  case $1 in
    --basedir) shift ; IB_BASEDIR=$1 ;; 
    --repo-user) shift ; REPO_USER=$1 ;; 
    --repo-server) shift ; REPO_SERVER=$1 ;; 
    --repo-path) shift ; REPO_PATH=$1 ;; 
    *) echo "Unknown command $1" ; exit 1 ;;
  esac
  shift
done

if [ "X$IB_BASEDIR" = X -o "X$REPO_USER" = X -o "X$REPO_SERVER" = X -o "X$REPO_PATH" = X ];then
  echo "Please provide all options"
  echo "Syntax: ./autoInstallLogs.sh --basedir <original log installation paths> --repo-user <repository user> --repo-server <repository server> --repo-path <repository path>"
  exit 1
fi

export LANG=C
# Remove from AFS logs for releases older than 7 days.
find $IB_BASEDIR -maxdepth 3 -mindepth 3 -mtime +6 -path '*/fwlite/CMSSW_*' -type d -exec rm -rf {} \; || true
for ib in $(find $IB_BASEDIR -maxdepth 6 -mindepth 6 -mtime +6 -path '*/www/*/CMSSW_*/new' -type d | sed 's|/new$||') ; do
  rm -rf $ib
done
# Remove empty <arch>/www/<day>/<rc>-<day>-<hour> directories
find $IB_BASEDIR -mindepth 4 -maxdepth 5 -path '*/www/*/*' -o -path '*/www/*/*/CMSSW_*' -type d | sed 's|/CMSSW_.*||' | sort | uniq -c | grep '1 ' | awk '{print $2}' | grep /www/ | xargs rm -rf || true
for WEEK in 0 1; do
  # notice it must finish with something which matches %Y-%m-%d-%H00
  # We only sync the last 7 days.
  XREPO_PATH=$REPO_PATH
  XDEPTH=2
  ssh -o StrictHostKeyChecking=no  $REPO_USER@$REPO_SERVER test -d $REPO_PATH/repos/cms.week$WEEK && XREPO_PATH="$REPO_PATH/repos" && XDEPTH=4 || true
  for logdir in $(ssh -o StrictHostKeyChecking=no  $REPO_USER@$REPO_SERVER find $XREPO_PATH/cms.week$WEEK/ -mindepth 2 -maxdepth $XDEPTH -path '*/WEB/build-logs' -type d) ; do
  BUILDS=`ssh -o StrictHostKeyChecking=no  $REPO_USER@$REPO_SERVER find $logdir -mtime -7 -mindepth 2 -maxdepth 2 -type d | sed 's|^.*/WEB/build-logs/||' | grep CMSSW | grep _X_ | grep '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9].*$' || true`
  for x in $BUILDS; do
    SCRAM_ARCH=`echo $x | cut -f1 -d/`
    REL_NAME=`echo $x | cut -f2 -d/`
    REL_TYPE=`echo $REL_NAME | sed -e's/.*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]\(.*\|\)$/new\1/'`
    CMSSW_NAME=`echo $REL_NAME | sed -e's/^\(CMSSW_.*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]\).*$/\1/'`
    CMSSW_DATE=`echo $CMSSW_NAME | sed -e's/.*\([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]\)$/\1/'`
    CMSSW_WEEKDAY=`python3 -c "import time;print time.strftime('%a', time.strptime('$CMSSW_DATE', '%Y-%m-%d-%H00')).lower()"`
    CMSSW_HOUR=`python3 -c "import time;print time.strftime('%H', time.strptime('$CMSSW_DATE', '%Y-%m-%d-%H00')).lower()"`
    CMSSW_QUEUE=`echo $CMSSW_NAME | sed -e's/_X_.*//;s/^CMSSW_//' | tr _ .`
    REL_LOGS_DIR="$IB_BASEDIR/$SCRAM_ARCH/www/$CMSSW_WEEKDAY/$CMSSW_QUEUE-$CMSSW_WEEKDAY-$CMSSW_HOUR/$CMSSW_NAME"
    REL_LOGS="${REL_LOGS_DIR}/${REL_TYPE}"
    mkdir -p $REL_LOGS || echo "Cannot create directory for $REL_LOGS"
    if [ ! -f ${REL_LOGS}/index.html ] ; then
      rsync -a --no-group --no-owner $REPO_USER@${REPO_SERVER}:$logdir/$x/logs/html/ $REL_LOGS/ || echo "Unable to sync logs in $REL_LOGS."
      ExtractLogs $REL_LOGS
    fi
    if [ "X$REL_TYPE" = "Xnew" ] ; then
      REL_TYPE="new_FWLITE"
      if [ -d $IB_BASEDIR/${SCRAM_ARCH}/fwlite/${CMSSW_NAME}/${REL_TYPE} ] ; then
        REL_LOGS="${REL_LOGS_DIR}/${REL_TYPE}"
        if [ ! -f ${REL_LOGS}/index.html ] ; then
          rsync -a --no-group --no-owner $IB_BASEDIR/${SCRAM_ARCH}/fwlite/${CMSSW_NAME}/${REL_TYPE}/ ${REL_LOGS}/
          ExtractLogs $REL_LOGS
        fi
      fi
    fi
  done
  done
done
