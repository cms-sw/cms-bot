#!/bin/bash -e

BRANCH="$1"

rm -rf stitched
git clone git@github.com:cms-sw/stitched
cd stitched
git checkout master
LAST_COMMIT=$(cat .cmssw-commit)
git remote add cmssw git@github.com:cms-sw/cmssw
git fetch cmssw $BRANCH:$BRANCH 
git checkout $BRANCH
git log --reverse --pretty=format:"%H" $LAST_COMMIT..$BRANCH > ../commits.txt
rm -rf ../cmssw
cp -rf ../stitched ../cmssw
git checkout master

I=0
CHGS=
for COMMIT in `cat ../commits.txt | grep '^[0-9a-f][0-9a-f]*$'` ; do 
  I=$(expr $I + 1)
  echo "WORKING ON $I: $COMMIT"
  FILES=
  for f in $(git diff-tree --no-commit-id --name-only -r $COMMIT) ; do
    pkg=$(echo $f | cut -d/ -f1,2)
    [ -d $pkg ] || continue
    FILES="$FILES $f"
  done
  [ "X$FILES" = "X" ] && continue
  pushd ../cmssw ; git checkout $COMMIT ; popd
  CHGS=YES
  echo "Applying patch $COMMIT"
  CHG_FILES=
  for f in $FILES ; do
    if [ -e ../cmssw/$f ] ; then
      CHG_FILES="$CHG_FILES $f"
    else
      rm -f $f
    fi
  done
  if [ "X$CHG_FILES" != "X" ] ; then
    git checkout $COMMIT -- $CHG_FILES
    for f in $CHG_FILES ; do
      if [ $(diff $f ../cmssw/$f | wc -l) -gt 0 ] ; then
        echo "File mismatch: $f"
        exit 1
      fi
    done
  fi
  echo $COMMIT > .cmssw-commit
  git add .
  git commit -a -C $COMMIT
done

pushd ../cmssw ; git checkout $COMMIT ; popd
echo "############ Checking extra changes ##############"
for d in $(ls) ; do
  for f in $(diff -aur $d ../cmssw/$d | grep "Only in ../cmssw/" | sed "s|.* ../cmssw/||;s|: *|/|") ; do
    pkg=$(echo $f | cut -d/ -f1,2)
    if [ -d $pkg ] ; then
      echo "Adding file: $f"
      mkdir -p $(dirname $f)
      cp ../cmssw/$f $f
      CHGS=YES
    fi
  done
  for f in $(diff -aur $d ../cmssw/$d | grep "Only in $d/" | sed "s|Only in *||;s|: *|/|") ; do
    echo "Deleting file: $f"
    rm -f $f
    CHGS=YES
  done
done

if [ $(diff -aur $d ../cmssw/$d | grep -v 'Only in ' | wc -l) -gt 0 ] ; then
  echo "Following difference are found"
  diff -aur $d ../cmssw/$d | grep -v 'Only in '
  exit 1
fi

if [ "X$CHGS" = "XYES" ] ; then
  git add .
  echo $COMMIT > .cmssw-commit
  git commit -a -m "sync changes cmssw $COMMIT"
fi

