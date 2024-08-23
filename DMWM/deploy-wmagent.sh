#! /bin/bash -e
start=`date +%s`

export DBSOCK=/tmp/`uuidgen`-mysql.sock

echo "Deploying wmagent@$WMAGENT_VERSION from $COMP_REPO"
$PWD/deployment/Deploy -R wmagent-dev@${WMAGENT_VERSION} -r comp=$COMP_REPO -t $WMAGENT_VERSION -A $DMWM_ARCH -s 'prep sw post' $PWD/deploy admin/devtools wmagent

perl -p -i -e 's/set-variable = innodb_buffer_pool_size=2G/set-variable = innodb_buffer_pool_size=50M/' deploy/current/config/mysql/my.cnf
perl -p -i -e 's/set-variable = innodb_log_file_size=512M/set-variable = innodb_log_file_size=20M/' deploy/current/config/mysql/my.cnf
perl -p -i -e 's/key_buffer=4000M/key_buffer=100M/' deploy/current/config/mysql/my.cnf
perl -p -i -e 's/max_heap_table_size=2048M/max_heap_table_size=100M/' deploy/current/config/mysql/my.cnf
perl -p -i -e 's/tmp_table_size=2048M/tmp_table_size=100M/' deploy/current/config/mysql/my.cnf

end=`date +%s`
runtime=$((end-start))

echo "Total time to deploy WMAgent: $runtime"
