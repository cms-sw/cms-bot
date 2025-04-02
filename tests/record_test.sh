#!/bin/bash

case $# in
  1)
    FLAGS="--record"
    ;;
  2)
    FLAGS="--record --record_action"
    ;;
  *)
    echo "USAGE: record_test <name> [<record_action>]";
    exit 1
    ;;
esac

pytest --log-disable=github.Requester --log-cli-level=DEBUG -k $1 $FLAGS --auth_with_token test_process_pr.py