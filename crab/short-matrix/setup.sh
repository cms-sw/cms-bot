#!/bin/bash -ex
scram build enable-multi-targets
cp $(dirname $0)/../FrameworkJobReport.xml $WORKSPACE/

