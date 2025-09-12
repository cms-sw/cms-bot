#!/bin/bash -xe
#VENV_DIR=venv
VENV_DIR=~/Work/cms-bot/.venv39
INSTALL_REQS=0
if [ ! -d $VENV_DIR ];  then
  python3 -m venv $VENV_DIR
  INSTALL_REQS=1
fi

source $VENV_DIR/bin/activate
if [ $INSTALL_REQS -eq 1 ]; then
  python3 -m pip install --upgrade pip
  pip install -r test-requirements.txt
fi

if [ ! -e Framework.py ]; then
  curl -L https://github.com/PyGithub/PyGithub/raw/v2.8.1/tests/Framework.py > Framework.py
  #sed -i -e 's/self\.retry/self.retry, per_page=100/g' Framework.py
  patch -p0 < Framework.patch
fi

if [ $# -ge 1 ]; then
  pytest --verbosity="2" -Wignore::DeprecationWarning -k "$@" test_process_pr.py --auth_with_token
else
  pytest --verbosity="2" -Wignore::DeprecationWarning test_process_pr.py --auth_with_token
fi
