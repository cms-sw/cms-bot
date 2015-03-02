#!/bin/sh -ex
if [ "X$1" = X ]; then
  echo "Please specify arch"
  exit 1
fi

if [ "X$2" = X ]; then
  echo "Please specify work directory (should be on local disk)"
  exit 1
fi

export SCRAM_ARCH=$1
export BASEDIR=$2
export BASEDESTDIR=/afs/cern.ch/cms/sw/ReleaseCandidates
export LANG=C

# Remove obsolete installations. We keep two not to break AFS vol0 and vol1 at
# any point.
find $BASEDIR -maxdepth 1 -mindepth 1 | sort -V | head -n -2 | xargs rm -rf

# The repositories we need to install are those for which we find the
# timestamp files:
REPOSITORIES=`find /afs/cern.ch/cms/sw/ReleaseCandidates/reset-repo-info -type f | tail -2 | xargs -n1 basename | sort -r -n`
echo $REPOSITORIES

# We install packages for both weeks. We reset every two week, alternating.
# Notice that the biweekly period for week 1 is shifted by 1 week for this
# reason we move it away from the 0 into 52 and take the modulo 52 afterward.
# Potentially we could separate the installation of the two volumes so that
# we don't need a huge local disk, but we can scatter this on different machienes.
for REPOSITORY in $REPOSITORIES; do
  echo $REPOSITORY
  WEEK=$(echo "$(echo $REPOSITORY | cut -d- -f2) % 2" | bc)
  WORKDIR=$BASEDIR/$REPOSITORY/$SCRAM_ARCH
  DESTDIR=$BASEDESTDIR/vol$WEEK
  mkdir -p $WORKDIR
  # Due to a bug in bootstrap.sh I need to install separate archs in separate directories.
  # This is because bootstraptmp is otherwise shared between different arches. Sigh.
  LOGFILE=$WORKDIR/bootstrap-$REPOSITORY.log
  # If the bootstrap log for the current two week period is not there
  # rebootstrap the area.
  if [ ! -f $LOGFILE ]; then
    # We move it so that if we are slow removing it, we do not endup removing
    # what got installed by someone else.
    mkdir -p $WORKDIR/common
    touch $LOGFILE
    wget -O $WORKDIR/bootstrap.sh http://cmsrep.cern.ch/cmssw/cms/bootstrap.sh
    sh -x $WORKDIR/bootstrap.sh setup -path $WORKDIR -r cms.week$WEEK -arch $SCRAM_ARCH >& $LOGFILE
    # We install locally, but we want to run from DESTDIR.
    echo "CMS_INSTALL_PREFIX='$DESTDIR'; export CMS_INSTALL_PREFIX" > $WORKDIR/common/apt-site-env.sh
  fi
  # Since we are installing on a local disk, no need to worry about
  # the rpm database.
  #
  # Make sure we do not mess up environment.
  # Also we do not want the installation of one release (which can be broken)
  # to interfere with the installation of a different one. For that reason we
  # ignore the exit code.
  (
    source $WORKDIR/$SCRAM_ARCH/external/apt/*/etc/profile.d/init.sh ;
    apt-get update ;
    apt-cache search cmssw-ib\\+CMSSW | cut -d\  -f1 | sort > onserver$$.txt ;
    rpm -qa --queryformat '%{NAME}\n' | grep cmssw-ib | sort > installed$$.txt ;
    for x in `diff -u onserver$$.txt installed$$.txt | grep -e '^-[^-]' | sed -e 's/^-//'`; do
      apt-get install -q -y $x || true;
      apt-get install -q -y `echo $x | sed -e 's/cmssw-ib/cmssw/'` || true;
      apt-get install -q -y `echo $x | sed -e 's/cmssw-ib/cmssw-patch/'` || true;
    done ;
    rm installed$$.txt ;
    rm onserver$$.txt ;
    apt-get clean
  ) || true
  # We create the directory in any case, to avoid the rsync to fail in case
  # the repository is not there and we cannot install.
  mkdir -p $WORKDIR/etc/
  rsync -a --no-group --no-owner $WORKDIR/etc/ $DESTDIR/etc/
done
REPOSITORIES=`find /afs/cern.ch/cms/sw/ReleaseCandidates/reset-repo-info -type f | tail -2 | xargs -n1 basename | sort -r -n`
echo $REPOSITORIES

# In order to avoid synchronizing the whole directories every time we do the
# following logic:
# - Get all the package directories
# - Check the source does not have a timestamp file in it called "done"
# - Do the rsync to destination.
# - Create the timestamp
# - Remove packages which are not in the source anymore.
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
    if [ ! -f  $WORKDIR/$PKG/done ]; then
      NEWPKG=`dirname $PKG`/tmp$$-`basename $PKG`
      mv $DESTDIR/$PKG $DESTDIR/$NEWPKG || mkdir -p $DESTDIR/$NEWPKG
      # We need to delete the temp directory in case of failure.
      (rsync -a -W --inplace --delete --no-group --no-owner $WORKDIR/$PKG/ $DESTDIR/$NEWPKG/ && mv -T $DESTDIR/$NEWPKG $DESTDIR/$PKG && touch $WORKDIR/$PKG/done) || rm -rf $DESTDIR/$NEWPKG || true
      #(mkdir -p $DESTDIR/$PKG/ ;rsync -a -W --delete --no-group --no-owner $WORKDIR/$PKG/ $DESTDIR/$PKG/ && touch $WORKDIR/$PKG/done) || true
    fi
    if [ ! -f $WORKDIR/$PKG/qa ]; then
      touch $WORKDIR/$PKG/qa
    fi
  done
  rm $DIRFILE
  for LEFTOVER in `find $DESTDIR -mindepth 3 -maxdepth 3 -type d -name "tmp*-*" | grep -e '.*/tmp[0-9][0-9]*-[^/][^/]*$'`; do
    OLD_PID=`basename $LEFTOVER | sed -e 's|.*/tmp\([0-9]*\)-.*|\1|'`
    if [ ! -d /proc/$OLD_PID ]; then
      # Do not die when weird AFS lock files are found.
      rm -rf $LEFTOVER || true
    fi
  done
done
