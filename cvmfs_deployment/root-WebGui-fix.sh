#!/bin/bash -e
dir=$1
[ "$dir" != "" ] || dir="/cvmfs/cms.cern.ch"
for r in $(find $dir -mindepth 4 -maxdepth 4  -path '*/lcg/root/6.*') ; do
  rver=$(basename $r | cut -d. -f2)
  [ $rver -ge 26 ] || continue
  f="${r}/etc/system.rootrc"
  if [ -e $r/etc/system.rootrc ] ; then
    #[ $(grep '^ *WebGui.HttpLoopback: *no' $f | wc -l) -gt 0 ] || continue
    echo "Processing $f"
    if [ -e  ${f}.original ] ; then
      cp ${f}.original $f
    else
      cp $f ${f}.original
    fi
    sed -i -e 's|WebGui.HttpLoopback: *no|WebGui.HttpLoopback:        yes|' $f
    sed -i -e 's|ROOT::Experimental::RWebBrowserImp|TRootBrowser|;s|ROOT::RWebBrowserImp|TRootBrowser|' $f
  fi
done
