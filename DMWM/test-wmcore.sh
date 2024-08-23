#! /bin/bash -e

start=`date +%s`

# ensure db exists
MYSQL_UNITTEST_DB=wmcore_unittest
mysql -u ${MYSQL_USER} --socket=${DBSOCK} --execute "CREATE DATABASE IF NOT EXISTS ${MYSQL_UNITTEST_DB}"
set -x

# working dir includes entire python source - ignore
perl -p -i -e 's/--cover-inclusive//' setup_test.py

#export NOSE_EXCLUDE='AlertGenerator'

# timeout tests after 5 mins
#export NOSE_PROCESSES=1
#export NOSE_PROCESS_TIMEOUT=300
#export NOSE_PROCESS_RESTARTWORKER=1

# cover branches but not external python modules
#FIXME: Is this working? No.
perl -p -i -e 's/--cover-inclusive/--cover-branches/' setup_test.py
perl -p -i -e "s/'--cover-html',//" setup_test.py

# include FWCore.ParameterSet.Config

export PYTHONPATH=/var/lib/jenkins/additional-library:$PYTHONPATH

# remove old coverage data
coverage erase

# run test - force success though - failure stops coverage report
rm nosetests*.xml || true
./cms-bot/DMWM/TestWatchdog.py &
python code/setup.py test --buildBotMode=true --reallyDeleteMyDatabaseAfterEveryTest=true --testCertainPath=code/test/python --testTotalSlices=$SLICES --testCurrentSlice=$SLICE || true #--testCertainPath=test/python/WMCore_t/WMBS_t || true
mv nosetests.xml nosetests-$SLICE-$BUILD_ID.xml

# Add these here as they need the same environment as the main run
#FIXME: change so initial coverage command skips external code
# coverage xml -i --include=$PWD/install* || true

#export PYLINTHOME=$PWD/.pylint.d # force pylint cache to this workspace
#ulimit -n 4086 # opens all source files at once (> 1024)
# pylint broken in latest build
#pylint --rcfile=code/standards/.pylintrc -f parseable install/lib/python2.7/site-packages/* 2>&1 > pylint.txt || true

end=`date +%s`
runtime=$((end-start))

echo "Total time to test slice $SLICE: $runtime"
