#! /bin/sh

current="none"
[ `ls -d deploy/current/sw*/$DMWM_ARCH/cms/wmagent/*` ] && current=$(basename $(ls -d deploy/current/sw*/$DMWM_ARCH/cms/wmagent/*))

# TODO: if a previous build leaves a corrupt install this will fail - how solve that - redeploy each time?

# if not provided get latest version
#WMAGENT_VERSION="0.8.14"
#WMAGENT_VERSION=$(curl -s http://cms-dmwm-builds.web.cern.ch/cms-dmwm-builds/wmagent.$SCRAM_ARCH.comp | awk '{print $4}' | cut -d+ -f3)

# fix -comp issue
# WHAT is this?   patch -N -d cfg -p2 < $HOME/wmagent_deploy_dash_name.patch || true

export DBSOCK=/tmp/$JENKINS_SERVER_COOKIE-$BUILD_ID-mysql.sock

if [ X$current != X$WMAGENT_VERSION ]; then
  echo "Deploying wmagent@$WMAGENT_VERSION"
  if [ -e $PWD/deploy ]; then
    echo "Stopping agent"
    [ -e $PWD/deploy/current/config/wmagent/manage ] && { $PWD/deploy/current/config/wmagent/manage stop-agent || true; }
    echo "Stopping services"
    [ -e $PWD/deploy/current/config/wmagent/manage ] && { $PWD/deploy/current/config/wmagent/manage stop-services || true; }
    # remove old crons
    #crontab -l
    crontab -r || true
    # hard kill any orphan processes
    pkill -9 -f $PWD/deploy || true
    pkill -9 -f $PWD/../.. || true
    rm -rf $PWD/deploy
    rm -rf $DBSOCK || true
  fi

  $PWD/deployment/Deploy -R wmagent-dev@${WMAGENT_VERSION} -r comp=comp.pre -t $WMAGENT_VERSION -A $DMWM_ARCH -s 'prep sw post' $PWD/deploy admin/devtools wmagent
fi

perl -p -i -e 's/set-variable = innodb_buffer_pool_size=2G/set-variable = innodb_buffer_pool_size=50M/' deploy/current/config/mysql/my.cnf
perl -p -i -e 's/set-variable = innodb_log_file_size=512M/set-variable = innodb_log_file_size=20M/' deploy/current/config/mysql/my.cnf
perl -p -i -e 's/key_buffer=4000M/key_buffer=100M/' deploy/current/config/mysql/my.cnf
perl -p -i -e 's/max_heap_table_size=2048M/max_heap_table_size=100M/' deploy/current/config/mysql/my.cnf
perl -p -i -e 's/tmp_table_size=2048M/tmp_table_size=100M/' deploy/current/config/mysql/my.cnf

