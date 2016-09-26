#!/bin/sh -ex
CMS_BOT_DIR=$(dirname $0)
case $CMS_BOT_DIR in /*) ;; *) CMS_BOT_DIR=$(pwd)/${CMS_BOT_DIR} ;; esac
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
CMS_WEEK=$5
export LANG=C

DELDIR=$BASEDIR/../delete/${SCRAM_ARCH}
mkdir -p $DELDIR

# The repositories we need to install are those for which we find the ib-week
REPOSITORIES=`tail -2 $CMS_BOT_DIR/ib-weeks | sed -e's/-\([0-9]\)$/-0\1/' | sort -r`
echo $REPOSITORIES | tr ' ' '\n' | xargs --no-run-if-empty -i mkdir -p "$BASEDIR/{}"

# Remove obsolete installations. We keep two not to break AFS vol0 and vol1 at
# any point.
find $BASEDIR -maxdepth 1 -mindepth 1 | sort -V | head -n -2 | xargs --no-run-if-empty -i mv '{}' ${DELDIR}/

# We install packages for both weeks. We reset every two week, alternating.
# Notice that the biweekly period for week 1 is shifted by 1 week for this
# reason we move it away from the 0 into 52 and take the modulo 52 afterward.
# Potentially we could separate the installation of the two volumes so that
# we don't need a huge local disk, but we can scatter this on different machienes.
for REPOSITORY in $REPOSITORIES; do
  echo $REPOSITORY
  WEEK=$(echo "$(echo $REPOSITORY | cut -d- -f2) % 2" | bc)
  if [ "X$CMS_WEEK" != "X" -a "$CMS_WEEK" != "cms.week$WEEK" ] ; then
    echo "Skipping week for $REPOSITORY"
    continue
  fi
  echo "Checking week $REPOSITORY ($WEEK) for RPMS"
  WORKDIR=$BASEDIR/$REPOSITORY/$SCRAM_ARCH
  DESTDIR=$BASEDESTDIR/vol$WEEK
  CMSPKG="$WORKDIR/common/cmspkg -a $SCRAM_ARCH"
  if [ ! -e $DESTDIR ] ; then DESTDIR=$BASEDESTDIR/$REPOSITORY ; fi
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
    wget --tries=5 --waitretry=60 -O $WORKDIR/bootstrap.sh http://cmsrep.cern.ch/cmssw/repos/bootstrap.sh
    sh -x $WORKDIR/bootstrap.sh setup -path $WORKDIR -r cms.week$WEEK -arch $SCRAM_ARCH >& $LOGFILE || (cat $LOGFILE && exit 1)
    # We install locally, but we want to run from DESTDIR.
    echo "CMS_INSTALL_PREFIX='$DESTDIR'; export CMS_INSTALL_PREFIX" > $WORKDIR/common/apt-site-env.sh
  fi
  if [ ! -d $WORKDIR/share/cms/cmspkg ] ; then
    wget --tries=5 --waitretry=60 -O $WORKDIR/cmspkg.py http://cmsrep.cern.ch/cmssw/repos/cmspkg.py
    chmod +x $WORKDIR/cmspkg.py
    $WORKDIR/cmspkg.tmp.py --repository cms.week$WEEK --architecture $SCRAM_ARCH --server cmsrep.cern.ch --path $WORKDIR setup
    rm -f $WORKDIR/cmspkg.py
  fi
  # Since we are installing on a local disk, no need to worry about
  # the rpm database.
  #
  # Make sure we do not mess up environment.
  # Also we do not want the installation of one release (which can be broken)
  # to interfere with the installation of a different one. For that reason we
  # ignore the exit code.
  (
    $CMSPKG update ;
    RELS_TO_INSTALL="" ;
    if [ "X$INSTALL_RELEASE" != "X" ] ; then
      RELS_TO_INSTALL="cms+cmssw-ib+$INSTALL_RELEASE" ;
    else
      $CMSPKG search cmssw-ib+CMSSW | cut -d\  -f1 | sort > onserver$$.txt ;
      $CMSPKG rpm -- -qa --queryformat '%{NAME}\n' | grep cmssw-ib | sort > installed$$.txt ;
      RELS_TO_INSTALL=`diff -u onserver$$.txt installed$$.txt | grep -e '^-[^-]' | sed -e 's/^-//'`;
    fi;
    for x in $RELS_TO_INSTALL; do
      $CMSPKG install -y $x || true;
      time $CMSPKG install -y `echo $x | sed -e 's/cmssw-ib/cmssw/'` || true;
      time $CMSPKG install -y `echo $x | sed -e 's/cmssw-ib/cmssw-patch/'` || true;
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
    $CMSPKG clean
  ) || true
  # We create the directory in any case, to avoid the rsync to fail in case
  # the repository is not there and we cannot install.
  mkdir -p $WORKDIR/etc/
  mkdir -p $WORKDIR/share
done

