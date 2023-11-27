#!/bin/bash -e
dir=$1
[ "$dir" != "" ] || dir="/cvmfs/cms.cern.ch"
for r in $(find $dir -mindepth 4 -maxdepth 4  -path '*/lcg/root/6.*') ; do
  rver=$(basename $r | cut -d. -f2)
  [ $rver -ge 26 ] || continue
  for f in $(find $r -maxdepth 2 -mindepth 2 -name 'system.rootrc' -type f) ; do
    [ $(grep '^ *WebGui.HttpLoopback: *no' $f | wc -l) -gt 0 ] || continue
    echo "Processing $f"
    cp $f ${f}.original
    sed -i -e 's|WebGui.HttpLoopback: *no|WebGui.HttpLoopback:        yes|' $f
  done
done
