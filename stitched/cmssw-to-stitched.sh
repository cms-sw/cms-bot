#!/bin/bash -e

BRANCH=CMSSW_8_1_X

rm -rf stitched cmssw
echo Cloning stitched
git clone -q -b master git@github.com:cms-sw/stitched
cd stitched
LAST_COMMIT=$(cat .cmssw-commit)
git remote add cmssw git@github.com:cms-sw/cmssw
echo Fetching cmssw
git fetch -q cmssw $BRANCH:$BRANCH
git checkout -q $BRANCH
git log --reverse --pretty=format:"%H" $LAST_COMMIT..$BRANCH > ../commits.txt
echo Making a copy of cmssw
rsync -a ../stitched/ ../cmssw/
git checkout -q master

I=0
T=$(cat ../commits.txt | wc -l)
CHGS=
for COMMIT in `cat ../commits.txt | grep '^[0-9a-f][0-9a-f]*$'` ; do
  I=$(expr $I + 1)
  echo "WORKING ON $I/$T: $COMMIT"
  FILES=
  for f in $(cd ../cmssw && git show --pretty="format:" --name-only $COMMIT | grep -v '^ *$') ; do
    pkg=$(echo $f | cut -d/ -f1,2)
    [ -d $pkg ] || continue
    FILES="$FILES $f"
  done
  [ "X$FILES" = "X" ] && continue
  cd ../cmssw ; git checkout -q $COMMIT ; cd ../stitched
  CHGS=YES
  echo "Applying patch $COMMIT"
  for f in $FILES ; do
    if [ -e ../cmssw/$f ] ; then
      mkdir -p $(dirname $f)
      cp -fp ../cmssw/$f $f
      echo "  +$f"
    else
      rm -f $f
      echo "  -$f"
    fi
  done
  echo $COMMIT > .cmssw-commit
  git add -A .
  git commit -a -C $COMMIT
done

[ "X$CHGS" = "X" ] && exit 0

cd ../cmssw ; git checkout -q $COMMIT ; cd ../stitched
echo "############ Checking extra changes ##############"
ERR=
for d in $(ls -d */*) ; do
  for f in $(diff -aur $d ../cmssw/$d | grep "Only in ../cmssw/" | sed "s|.* ../cmssw/||;s|: *|/|") ; do
    echo "Missing: $f"
    ERR=YES
  done
  for f in $(diff -aur $d ../cmssw/$d | grep "Only in $d/" | sed "s|Only in *||;s|: *|/|") ; do
    echo "New: $f"
    ERR=YES
  done
  if [ $(diff -aur $d ../cmssw/$d | grep -v 'Only in ' | wc -l) -gt 0 ] ; then
    echo "Following difference are found"
    diff -aur $d ../cmssw/$d | grep -v 'Only in '
    ERR=YES
  fi
done

[ "X$ERR" = "XYES" ] && exit 1

echo $COMMIT > .cmssw-commit
git commit -a -m "sync changes cmssw $COMMIT"

