#!/bin/bash
coverage run --include=../process_pr.py -m pytest --auth_with_token test_process_pr.py
coverage html
if [ $(hostname) = "cmspc001" ]; then
  ssh lxplus rm -rf /eos/user/r/razumov/www/htmlcov
  scp -r htmlcov lxplus:/eos/user/r/razumov/www/
fi