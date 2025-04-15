#!/bin/bash -xe
INSTALL_REQS=0
if [ ! -d venv ];  then
  python3.9 -m venv venv
  INSTALL_REQS=1
fi

source venv/bin/activate
if [ $INSTALL_REQS -eq 1 ]; then
  python3 -m pip install --upgrade pip
  pip install -r test-requirements.txt
fi

if [ ! -e Framework.py ]; then
  curl -L https://github.com/PyGithub/PyGithub/raw/v1.54/tests/Framework.py > Framework.py
  sed -i -e 's/self\.retry/self.retry, per_page=100/g' Framework.py
fi

if [ $# -ge 1 ]; then
  pytest -k $@ test_process_pr.py --auth_with_token
else
  pytest test_process_pr.py --auth_with_token
fi
