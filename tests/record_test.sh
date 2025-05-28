#!/bin/bash -xe

case $2 in
  1)
    FLAGS="--record"
    ;;
  2)
    FLAGS="--record_action"
    ;;
  3)
    FLAGS="--record --record_action"
    ;;
  *)
    echo "USAGE: record_test <name> [<mode>]";
    exit 1
    ;;
esac

pytest -Wignore::DeprecationWarning --log-disable=github.Requester --log-cli-level=DEBUG -k $1 $FLAGS --auth_with_token test_process_pr.py
./verify_load_cache.py