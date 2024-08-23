#! /bin/bash -e

start=`date +%s`

# ensure db exists
MYSQL_UNITTEST_DB=wmcore_unittest
mysql -u ${MYSQL_USER} --socket=${DBSOCK} --execute "CREATE DATABASE IF NOT EXISTS ${MYSQL_UNITTEST_DB}"
set -x

### Some tweaks for the nose run (in practice, there is nothing to change in setup_test.py...)
# working dir includes entire python source - ignore
perl -p -i -e 's/--cover-inclusive//' code/setup_test.py
# cover branches but not external python modules
perl -p -i -e 's/--cover-inclusive/--cover-branches/' code/setup_test.py
perl -p -i -e "s/'--cover-html',//" code/setup_test.py

#export NOSE_EXCLUDE='AlertGenerator'
# timeout tests after 5 mins
#export NOSE_PROCESSES=1
#export NOSE_PROCESS_TIMEOUT=300
#export NOSE_PROCESS_RESTARTWORKER=1

# include FWCore.ParameterSet.Config

export PYTHONPATH=/var/lib/jenkins/additional-library:$PYTHONPATH

# remove old coverage data
coverage erase

# debugging python interpreters
echo "Python version is: " && python --version || true
echo "Python3 version is: " && python3 --version || true

# run test - force success though - failure stops coverage report
rm nosetests*.xml || true
# FIXME Alan on 25/may/2021: ImportError: cannot import name _psutil_linux
#python3 cms-bot/DMWM/TestWatchdog.py &

python3 code/setup.py test --buildBotMode=true --reallyDeleteMyDatabaseAfterEveryTest=true --testCertainPath=code/test/python --testTotalSlices=$SLICES --testCurrentSlice=$SLICE || true #--testCertainPath=test/python/WMCore_t/WMBS_t || true
mv nosetests.xml nosetestspy3-$SLICE-$BUILD_ID.xml

# Add these here as they need the same environment as the main run
#FIXME: change so initial coverage command skips external code
# coverage xml -i --include=$PWD/install* || true

end=`date +%s`
runtime=$((end-start))

echo "Total time to test slice $SLICE: $runtime"
