#!/bin/bash
coverage run --include=../process_pr.py -m pytest --auth_with_token test_process_pr.py
coverage html
if [ $(hostname) = "cmspc01" ]; then
  ssh lxplus rm -rf /eos/user/r/razumov/www/htmlcov
  scp htmlcov lxplus:/eos/user/r/razumov/www/
fi