#!/bin/sh -ex
if [ "X$1" = X ]; then
  echo "Please specify arch"
  exit 1
fi

if [ "X$2" = X ]; then
  echo "Please specify work directory (should be on local disk)"
  exit 1
fi

if [ "X$3" = X ]; then
  echo "Please specify destination directory (e.g. /afs/cern.ch/cms/sw/ReleaseCandidates)"
  exit 1
fi

export SCRAM_ARCH=$1
export BASEDIR=$2
export BASEDESTDIR=$3
export LANG=C

# The repositories we need to install are those for which we find the
# timestamp files:
REPOSITORIES=`find $BASEDESTDIR/reset-repo-info -type f | tail -2 | xargs -n1 basename | sort -r -n`
echo $REPOSITORIES | tr ' ' '\n' | xargs --no-run-if-empty -i mkdir -p "$BASEDIR/{}"

# In order to avoid synchronizing the whole directories every time we do the
# following logic:
# - Get all the package directories
# - Check the source does not have a timestamp file in it called "done"
# - Do the rsync to destination.
# - Create the timestamp
# - Remove packages which are not in the source anymore.
REPOSITORIES="2016-5"
for REPOSITORY in $REPOSITORIES; do
  WEEK=$(echo "$(echo $REPOSITORY | cut -d- -f2) % 2" | bc)
  WORKDIR=$BASEDIR/$REPOSITORY/$SCRAM_ARCH/$SCRAM_ARCH
  DESTDIR=$BASEDESTDIR/vol$WEEK/$SCRAM_ARCH
  DIRFILE=$WORKDIR/dirs$$.txt
  # Again, we create the WORKDIR to handle the case we cannot bootstrap one of
  # the reposiries.
  mkdir -p $WORKDIR
  find $WORKDIR -mindepth 3 -maxdepth 3 -type d | sed -e "s|.*$SCRAM_ARCH/||" > $DIRFILE
  set +e
  find $DESTDIR -mindepth 3 -maxdepth 3 -type d | sed -e "s|.*$SCRAM_ARCH/||"| grep -v -e '.*/tmp[0-9][0-9]*-[^/][^/]*$'  >> $DIRFILE
  set -e
  for REMOVED in `cat $DIRFILE | sort | uniq -c | grep -e "^ " | grep -e '^[^1]*1 '| sed -e's/^[^1]*1 //'`; do
    (pushd $DESTDIR ; rm -rf $REMOVED; popd)
  done
  for PKG in `find $WORKDIR/ -mindepth 3 -maxdepth 3 -type d | sort -r | sed -e "s|.*$SCRAM_ARCH/||"`; do
    [ -f  $WORKDIR/$PKG/done ] && continue
    NEWPKG=`dirname $PKG`/tmp$$-`basename $PKG`
    mv $DESTDIR/$PKG $DESTDIR/$NEWPKG || mkdir -p $DESTDIR/$NEWPKG
    # We need to delete the temp directory in case of failure.
    (rsync -a -W --inplace --delete --no-group --no-owner $WORKDIR/$PKG/ $DESTDIR/$NEWPKG/ && mv -T $DESTDIR/$NEWPKG $DESTDIR/$PKG && touch $WORKDIR/$PKG/done) || rm -rf $DESTDIR/$NEWPKG || true
  done
  rsync -a --no-group --no-owner $WORKDIR/../etc/ $DESTDIR/../etc/ || true
  rm $DIRFILE
  for LEFTOVER in `find $DESTDIR -mindepth 3 -maxdepth 3 -type d -name "tmp*-*" | grep -e '.*/tmp[0-9][0-9]*-[^/][^/]*$'`; do
    OLD_PID=`basename $LEFTOVER | sed -e 's|.*/tmp\([0-9]*\)-.*|\1|'`
    if [ ! -d /proc/$OLD_PID ]; then
      # Do not die when weird AFS lock files are found.
      rm -rf $LEFTOVER || true
    fi
  done
done

