#!/bin/bash -e
env > run.log
ld.so --help | grep supported | grep x86-64-v
mkdir matrix
pushd matrix
  runTheMatrix.py -i all -s -j 3 -t 4 --ibeos >>../run.log 2>&1 || touch runall-report-step123-.log
  for f in $(find . -name '*' -type f) ; do
    case $f in
      *.xml|*.txt|*.log|*.py|*.json|*/cmdLog ) ;;
      * ) rm -rf $f ;;
    esac
  done
popd
mv matrix/runall-report-step123-.log matrix.log
tar -czvf matrix.tar.gz matrix
