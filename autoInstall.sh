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
export INSTALL_RELEASE=$4
export LANG=C

DELDIR=$BASEDIR/../delete/${SCRAM_ARCH}
mkdir -p $DELDIR

# The repositories we need to install are those for which we find the
# timestamp files:
REPOSITORIES=`find $BASEDESTDIR/reset-repo-info -type f | tail -2 | xargs -n1 basename | sort -r -n`
echo $REPOSITORIES | tr ' ' '\n' | xargs --no-run-if-empty -i mkdir -p "$BASEDIR/{}"

# Remove obsolete installations. We keep two not to break AFS vol0 and vol1 at
# any point.
find $BASEDIR -maxdepth 1 -mindepth 1 | sort -V | head -n -2 | xargs --no-run-if-empty -i mv '{}' ${DELDIR}/

# We install packages for both weeks. We reset every two week, alternating.
# Notice that the biweekly period for week 1 is shifted by 1 week for this
# reason we move it away from the 0 into 52 and take the modulo 52 afterward.
# Potentially we could separate the installation of the two volumes so that
# we don't need a huge local disk, but we can scatter this on different machienes.
REPOSITORIES="2016-4"
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
    RELS_TO_INSTALL="" ;
    if [ "X$INSTALL_RELEASE" != "X" ] ; then
      RELS_TO_INSTALL="cms+cmssw-ib+$INSTALL_RELEASE" ;
    else
      apt-cache search cmssw-ib\\+CMSSW | cut -d\  -f1 | sort > onserver$$.txt ;
      rpm -qa --queryformat '%{NAME}\n' | grep cmssw-ib | sort > installed$$.txt ;
      RELS_TO_INSTALL=`diff -u onserver$$.txt installed$$.txt | grep -e '^-[^-]' | sed -e 's/^-//'`;
    fi;
    for x in $RELS_TO_INSTALL; do
      apt-get install -q -y $x || true;
      apt-get install -q -y `echo $x | sed -e 's/cmssw-ib/cmssw/'` || true;
      apt-get install -q -y `echo $x | sed -e 's/cmssw-ib/cmssw-patch/'` || true;
      relname=`echo $x | awk -F + '{print $NF}'` ;
      timestamp=`echo $relname | awk -F _ '{print $NF}' | grep '^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]$' | sed 's|-||g'` ;
      if [ "X$timestamp" != "X" ] ; then
        for y in cmssw cmssw-patch ; do
          if [ -d $WORKDIR/$SCRAM_ARCH/cms/$y/$relname ] ; then
            touch -t $timestamp $WORKDIR/$SCRAM_ARCH/cms/$y/$relname ;
          fi
        done ;
      fi
    done ;
    rm -f installed$$.txt ;
    rm -f onserver$$.txt ;
    apt-get clean
  ) || true
  # We create the directory in any case, to avoid the rsync to fail in case
  # the repository is not there and we cannot install.
  mkdir -p $WORKDIR/etc/
done

