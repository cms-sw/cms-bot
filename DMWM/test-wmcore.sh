# ensure db exists
echo "CREATE DATABASE IF NOT EXISTS WMCore_unit_test" | mysql -u ${MYSQL_USER} --password=${MYSQL_PASS} --socket=${DBSOCK}
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
python code/setup.py test --buildBotMode=true --reallyDeleteMyDatabaseAfterEveryTest=true --testCertainPath=code/test/python --testTotalSlices=10 --testCurrentSlice=$SLICE || true #--testCertainPath=test/python/WMCore_t/WMBS_t || true
cp nosetests.xml nosetests-$SLICE.xml

# Add these here as they need the same environment as the main run
#FIXME: change so initial coverage command skips external code
coverage xml -i --include=$PWD/install* || true

export PYLINTHOME=$PWD/.pylint.d # force pylint cache to this workspace
ulimit -n 4086 # opens all source files at once (> 1024)
pylint --rcfile=code/standards/.pylintrc -f parseable install/lib/python2.6/site-packages/* 2>&1 > pylint.txt || true
