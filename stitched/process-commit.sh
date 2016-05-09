#!/bin/bash -ex

COMMIT="$1"
DIR=$(/bin/pwd)
COMMIT_STORE="$DIR/commits/$(echo $COMMIT | cut -c1-2)/$COMMIT"
[ -f $COMMIT_STORE/done ] && exit 0
[ -d $DIR/stitched ] || exit 1
cd $DIR/stitched
rm -rf $COMMIT_STORE
mkdir -p $COMMIT_STORE
PACKAGES="$DIR/commits/packages"
git log -n 1 --oneline --name-only $COMMIT | grep -v ' ' > $COMMIT_STORE/all.files || true
grep -f $PACKAGES $COMMIT_STORE/all.files  > $COMMIT_STORE/files || true
if [ "X$(cat $COMMIT_STORE/files | wc -l)" != "X0" ] ; then
  git show --oneline $COMMIT | grep -v '^\(index\|diff\) ' > $COMMIT_STORE/diff
  cd $COMMIT_STORE
  splitdiff -a diff > /dev/null
  for f in $(ls diff.part*) ; do
    FILE=$(head -2 $f | grep '^[-+]\{3\} [ab]/' | head -1 | sed 's|.* [ab]/||')
    if [ "X$FILE" = "X" ] ; then
      echo "No file found: $COMMIT"
      exit 1
    fi
    if [ $(grep "^$FILE\$" files | wc -l) = 0 ] ; then
      rm -f $f
    fi
  done
  rm -f diff
  cat diff.part* > stitched.patch
fi
touch $COMMIT_STORE/done
