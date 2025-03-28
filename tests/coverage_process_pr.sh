#!/bin/bash
coverage run -m pytest --auth_with_token test_process_pr.py
coverage html
