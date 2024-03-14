#!/bin/bash -xe

if [ $# -ne 1 ];
then
  echo Usage: run.sh testname
  exit 1
fi

pushd ..
python3.6 process-pull-request.py -n -r iarspider-cmssw/cmssw 15 > log.txt
grep log.txt -e '^Changed Labels'
grep log.txt -ie '^DRY RUN'
popd
read -p "Press enter to continue"
pytest -k $1 --record --auth_with_token
pytest -k $1 --auth_with_token
#read -p "Press enter to continue"
pushd ..
python3.6 process-pull-request.py -r iarspider-cmssw/cmssw 15
popd
