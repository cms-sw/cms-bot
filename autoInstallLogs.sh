#!/bin/sh -e
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
find $IB_BASEDIR -maxdepth 5 -mindepth 5 -mtime +6 -path '*/www/*/CMSSW_*' -type d -exec rm -rf {} \; || true
# Remove empty <arch>/www/<day>/<rc>-<day>-<hour> directories
find $IB_BASEDIR -mindepth 4 -maxdepth 5 -path '*/www/*/*' -o -path '*/www/*/*/CMSSW_*' -type d | sed 's|/CMSSW_.*||' | sort | uniq -c | grep '1 ' | awk '{print $2}' | grep /www/ | xargs rm -rf || true
for WEEK in 0 1; do
  BIWEEK=`echo "((52 + $(date +%W) - $WEEK)/2)%26" | bc`
  # notice it must finish with something which matches %Y-%m-%d-%H00
  # We only sync the last 7 days.
  BUILDS=`ssh $REPO_USER@$REPO_SERVER find $REPO_PATH/cms.week$WEEK/WEB/build-logs/ -mtime -7 -mindepth 2 -maxdepth 2 | cut -d/ -f7,8 | grep CMSSW | grep _X_ | grep '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9].*$' || true`
  for x in $BUILDS; do
    SCRAM_ARCH=`echo $x | cut -f1 -d/`
    REL_NAME=`echo $x | cut -f2 -d/`
    REL_TYPE=`echo $REL_NAME | sed -e's/.*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]\(.*\|\)$/new\1/'`
    CMSSW_NAME=`echo $REL_NAME | sed -e's/^\(CMSSW_.*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]\).*$/\1/'`
    CMSSW_DATE=`echo $CMSSW_NAME | sed -e's/.*\([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]\)$/\1/'`
    CMSSW_WEEKDAY=`python -c "import time;print time.strftime('%a', time.strptime('$CMSSW_DATE', '%Y-%m-%d-%H00')).lower()"`
    CMSSW_HOUR=`python -c "import time;print time.strftime('%H', time.strptime('$CMSSW_DATE', '%Y-%m-%d-%H00')).lower()"`
    CMSSW_QUEUE=`echo $CMSSW_NAME | sed -e's/_X_.*//;s/^CMSSW_//' | tr _ .`
    REL_LOGS="$IB_BASEDIR/$SCRAM_ARCH/www/$CMSSW_WEEKDAY/$CMSSW_QUEUE-$CMSSW_WEEKDAY-$CMSSW_HOUR/$CMSSW_NAME/${REL_TYPE}"
    if [ -L $REL_LOGS ]; then
      rm -rf $REL_LOGS
    fi
    mkdir -p $REL_LOGS || echo "Cannot create directory for $REL_LOGS"
    rsync -a --no-group --no-owner $REPO_USER@${REPO_SERVER}:$REPO_PATH/cms.week$WEEK/WEB/build-logs/$x/logs/html/ $REL_LOGS/ || echo "Unable to sync logs in $REL_LOGS."
    pushd $REL_LOGS
      if [ -f html-logs.zip ] ; then
        [ -f logAnalysis.pkl ] || (unzip -p html-logs.zip logAnalysis.pkl > logAnalysis.pkl || echo "Unable to unpack logs in $REL_LOGS.")
        [ -f index.html ] || (unzip -p html-logs.zip index.html >  index.html || echo "Unable to unpack logs in $REL_LOGS.")
      fi
    popd
  done
done
