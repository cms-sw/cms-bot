#!/bin/bash
cd $CMSSW_BASE
for x in $(ls -d src-*) ; do
  pushd $x
    b=$(git branch --show-current)
    git push my-cmssw $b
  popd
done
