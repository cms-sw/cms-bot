#!/bin/bash -e

BRANCH="$1"
DIR=$(/bin/pwd)
COMMIT_STORE="$DIR/commits"
[ -f $DIR/commits/commits.txt ] || exit 1

cd $DIR/stitched
git checkout master
I=0
CHGS=
for COMMIT in `cat $DIR/commits/commits.txt | grep '^[0-9a-f][0-9a-f]*$'` ; do 
  I=$(expr $I + 1)
  echo "WORKING ON $I: $COMMIT"
  COMMIT_STORE="$DIR/commits/$(echo $COMMIT | cut -c1-2)/$COMMIT"
  [ -f $COMMIT_STORE/apply ] && continue
  [ -f $COMMIT_STORE/done ] || exit 1
  if [ ! -f $COMMIT_STORE/stitched.patch ] ; then
    touch $COMMIT_STORE/apply
    continue
  fi
  echo "Applying patch $COMMIT"
  REV=$(patch -p1 -N --dry-run < $COMMIT_STORE/stitched.patch | grep 'Reversed .* patch detected' | wc -l)
  CHGS=YES
  if [ "X$REV" = "X0" ] ; then
    echo "Apply $COMMIT"
    patch -p1 < $COMMIT_STORE/stitched.patch
    echo $COMMIT > .cmssw-commit
    git add .
    git commit -a -C $COMMIT
  else
    echo "Reverse patch"
  fi
  touch $COMMIT_STORE/apply
done
if [ "X$CHGS" = "XYES" ] ; then
  echo $COMMIT > .cmssw-commit
  git commit -a -m "sync changes from cms-sw/cmssw using $COMMIT"
fi

