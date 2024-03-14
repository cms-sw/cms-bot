#!/bin/bash -xe

if [ $# -ne 1 ];
then
  echo Usage: run.sh testname
  exit 1
fi

pushd ..
echo ==================== DRY-RUN ====================
python3.6 process-pull-request.py -n -r iarspider-cmssw/cmssw 18 > log.txt
grep log.txt -e '^Changed Labels' || true
grep log.txt -ie '^DRY RUN' || true
popd
read -p "Press enter to continue"
echo ==================== RECORD ====================
python3.6 -m pytest -k $1 --record --auth_with_token
read -p "Press enter to continue"
echo ==================== REPLAY ====================
python3.6 -m pytest -k $1 --auth_with_token
read -p "Press enter to continue"
pushd ..
echo ==================== DO WORK ====================
python3.6 process-pull-request.py -r iarspider-cmssw/cmssw 18
popd
