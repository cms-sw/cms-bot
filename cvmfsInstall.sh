#!/bin/sh -ex
ARCHITECTURE=$1
CMS_WEEK=$2
RELEASE_NAME=$3
WORKSPACE=$4
DEV=$5
USE_DEV=""
if [ "X$DEV" = "Xtrue" ] ; then
  DEV="-dev"
  USE_DEV="--use-dev"
else
  DEV=""
fi

PROOTDIR=$6
if [ "X$PROOTDIR" = "X" ] ; then
  PROOTDIR=/build/cmsbuild/proot
fi

export PROOTDIR
cd $PROOTDIR
PROOT_URL="https://cmssdt.cern.ch/proot/"
echo "[PROOT] Mirroring files from "$PROOT_URL
NEW_PKG=$(wget -nv -r -nH -nd -np -m -R *.html* $PROOT_URL 2>&1 | grep -v html | grep URL | grep tar.bz2 | cut -d\" -f2)
#Unpack any new/updated archive downloaded
for arch in $NEW_PKG; do
  DIR=$( echo $arch | sed -r 's/.tar.bz2//')
  if [ -d $DIR ]; then
    echo "[PROOT] Removing obsolete unpacked dir"
    mv $DIR removeMe
    chmod -R 700 removeMe
    rm -rf removeMe
  fi
  echo "[PROOT] Unpacking "$arch
  tar xjf $arch
done

cd $WORKSPACE/cms-bot
[ -f ib-weeks ] || exit 1

export CMSIB_CVMFS_REPO=cms-ib.cern.ch
export BASEDIR=/cvmfs/$CMSIB_CVMFS_REPO
export BASEDESTDIR=/cvmfs/$CMSIB_CVMFS_REPO
export THISDIR=`pwd`
export LANG=C
# The disk where cvmfs is mounted
if [ -d /srv/cvmfs/$CMSIB_CVMFS_REPO/data/ ]; then
  export DISK="/srv/cvmfs/$CMSIB_CVMFS_REPO/data/"
elif [ -d /var/spool/cvmfs/$CMSIB_CVMFS_REPO/$CMSIB_CVMFS_REPO/data/ ]; then
  export DISK="/var/spool/cvmfs/$CMSIB_CVMFS_REPO/$CMSIB_CVMFS_REPO/data/"
else
  export DISK="/dev/vdc"
fi
export INITIAL_SIZE=`df -B 1M $DISK | awk '{print $3}' | tail -1`
# Size in Mb to trigger publishing, this avoid huge publishing time (note at 3.6 Mb/s 13000 Mb is roughly 1 hr)
export PUBLISH_THRESHOLD=13000
# The repositories we need to install are those for which we find the
# timestamp files:
REPOSITORIES=`tail -2 ib-weeks | sed -e's/-\([0-9]\)$/-0\1/' | sort -r`

echo $REPOSITORIES
ARCHITECTURES=$ARCHITECTURE
#If Architecture is not pass via command line then check for all ARCHS from the config.map file
if [ "X$ARCHITECTURE" = "X" ] ; then
  ARCHITECTURES=`curl -s https://raw.githubusercontent.com/cms-sw/cms-bot/HEAD/config.map | grep -v DISABLED= | grep -o "slc[5-7]_amd64_gcc[0-9][0-9][0-9]" | sort -ur` #Reverse order to install most important IBs first
fi

echo $ARCHITECTURES
# Prepare the cvmfs repository in read/write mode
cvmfs_server transaction || ((cvmfs_server abort -f || rm -fR /var/spool/cvmfs/cms-ib.cern.ch/is_publishing.lock) && cvmfs_server transaction)
# Check if the transaction really happened
if [ `touch $BASEDIR/is_writable 2> /dev/null; echo "$?"` -eq 0 ]; then
rm $BASEDIR/is_writable
else
echo CVMFS filesystem is not writable. Aborting.
echo " " | mail -s "$CMSIB_CVMFS_REPO cannot be set to transaction" cms-sdt-logs@cern.ch
exit 1
fi

# Create Nested Catalogs file if it doesn't exist
if [ ! -f $BASEDIR/.cvmfsdirtab ]; then
cat <<EOF > $BASEDIR/.cvmfsdirtab
/*/share
/*/*_*_*/external
/*/*_*_*/external/blackhat/*
/*/*_*_*/external/geant4/*
/*/*_*_*/external/boost/*
/*/*_*_*/cms
/*/*_*_*/lcg
/*/*_*_*/cms/cmssw/*
/*/*_*_*/cms/cmssw-patch/*
EOF
fi

if [ $(ls -d $BASEDIR/20* | wc -l) -gt 0 ] ; then
  OLD_WEEKS=$(ls -d $BASEDIR/20*)
  # Cleanup old weeks
  find $BASEDIR/* -maxdepth 0 -type d -not \( -name "`echo $REPOSITORIES | awk '{print $1}'`" -or -name "`echo $REPOSITORIES | awk '{print $2}'`" \) | xargs rm -rf
fi
# Remove all existing links for week[0-1]
for link in $(find $BASEDESTDIR/* -maxdepth 0 -type l); do unlink $link; done;
# Recreate links week[0-1]
for dir in $(find $BASEDESTDIR/* -maxdepth 0 -type d | grep -G "20[0-9][0-9]-[0-5][0-9]"); do ln -s $dir $( dirname $dir )/week$(( 10#$( echo $( basename $dir ) | cut -d"-" -f 2 )%2 )); done;

dockerrun()
{
  case "$SCRAM_ARCH" in
    slc6_amd64_* )
      ARGS="cd $THISDIR; $@"
      docker run --rm -t -e THISDIR=${THISDIR} -e WORKDIR=${WORKDIR} -e SCRAM_ARCH=${SCRAM_ARCH} -e x=${x} -v /tmp:/tmp -v ${WORKDIR}:${WORKDIR} -v ${THISDIR}:${THISDIR} -u $(whoami) cmssw/slc6-installer:latest sh -c "$ARGS"
      ;;
    slc7_amd64_* )
      ARGS="cd $THISDIR; $@"
      docker run --rm -t -e THISDIR=${THISDIR} -e WORKDIR=${WORKDIR} -e SCRAM_ARCH=${SCRAM_ARCH} -e x=${x} -v /tmp:/tmp -v ${WORKDIR}:${WORKDIR} -v ${THISDIR}:${THISDIR} -u $(whoami) cmssw/slc7-installer:latest sh -c "$ARGS"
      ;;
    slc7_aarch64_* )
      ARGS="export THISDIR=${THISDIR}; export WORKDIR=${WORKDIR}; export SCRAM_ARCH=${SCRAM_ARCH}; export x=${x}; cd ${THISDIR}; $@"
      $PROOTDIR/proot -R $PROOTDIR/centos-7.2.1511-aarch64-rootfs -b /tmp:tmp -b /build:/build -b /cvmfs:/cvmfs -w ${THISDIR} -q "$PROOTDIR/qemu-aarch64 -cpu cortex-a57" sh -c "$ARGS"
      ;;
    fc24_ppc64le_* )
      ARGS="export THISDIR=${THISDIR}; export WORKDIR=${WORKDIR}; export SCRAM_ARCH=${SCRAM_ARCH}; export x=${x}; cd ${THISDIR}; $@"
      $PROOTDIR/proot -R $PROOTDIR/fedora-24-ppc64le-rootfs -b /tmp:/tmp -b /build:/build -b /cvmfs:/cvmfs -w ${THISDIR} -q "$PROOTDIR/qemu-ppc64le -cpu POWER8" sh -c "$ARGS"
      ;;
    slc7_ppc64le_* )
      ARGS="export THISDIR=${THISDIR}; export WORKDIR=${WORKDIR}; export SCRAM_ARCH=${SCRAM_ARCH}; export x=${x}; cd ${THISDIR}; $@"
      $PROOTDIR/proot -R $PROOTDIR/centos-7.2.1511-ppc64le-rootfs -b /tmp:/tmp -b /build:/build -b /cvmfs:/cvmfs -w ${THISDIR} -q "$PROOTDIR/qemu-ppc64le -cpu POWER8" sh -c "$ARGS"
      ;;
    * )
      eval $@
      ;;
  esac
}


# We install packages for both weeks. We reset every two week, alternating.
# Notice that the biweekly period for week 1 is shifted by 1 week for this
# reason we move it away from the 0 into 52 and take the modulo 52 afterward.
# Potentially we could separate the installation of the two volumes so that
# we don't need a huge local disk, but we can scatter this on different machienes.
TMP_PREFIX=/tmp/cvsmfs-$$
for REPOSITORY in $REPOSITORIES; do
  echo $REPOSITORY
  WEEK=$(echo "$(echo $REPOSITORY | cut -d- -f2) % 2" | bc)
  #If CMS_WEEK was set then only check releases for that week
  if [ "X$CMS_WEEK" != "X" -a "$CMS_WEEK" != "cms.week$WEEK" ] ; then
    echo "Skipping week for $REPOSITORY"
    continue
  fi
  echo "Checking week $REPOSITORY ($WEEK) for RPMS"
  WORKDIR=$BASEDIR/$REPOSITORY
  mkdir -p $WORKDIR
  # Install all architectures of the most recent week first.
  for SCRAM_ARCH in $ARCHITECTURES; do
    CMSPKG="$WORKDIR/common/cmspkg -a $SCRAM_ARCH ${USE_DEV}"
    # Due to a bug in bootstrap.sh I need to install separate archs in separate directories.
    # This is because bootstraptmp is otherwise shared between different arches. Sigh.
    LOGFILE=$WORKDIR/bootstrap-$REPOSITORY-$SCRAM_ARCH.log
    #Recover from bad bootstrap arch
    if [ -f $LOGFILE -a ! -f $WORKDIR/$SCRAM_ARCH/cms/cms-common/1.0/etc/profile.d/init.sh ] ; then
      rm -f $LOGFILE
    fi
    # If the bootstrap log for the current two week period is not there
    # rebootstrap the area.
    if [ ! -f $LOGFILE ]; then
      # We move it so that if we are slow removing it, we do not endup removing
      # what got installed by someone else.
      rm -rf $WORKDIR/$SCRAM_ARCH
      rm -rf $WORKDIR/bootstraptmp
      wget --tries=5 --waitretry=60 -O $WORKDIR/bootstrap.sh http://cmsrep.cern.ch/cmssw/repos/bootstrap${DEV}.sh
      dockerrun "sh -ex $WORKDIR/bootstrap.sh setup ${DEV} -path $WORKDIR -r cms.week$WEEK -arch $SCRAM_ARCH -y >& $LOGFILE" || (cat $LOGFILE && exit 1)
      dockerrun "$CMSPKG install -y cms+local-cern-siteconf+sm111124 || true"
    fi
    $CMSPKG -y upgrade
    RPM_CONFIG=$WORKDIR/${SCRAM_ARCH}/var/lib/rpm/DB_CONFIG
    if [ ! -e $RPM_CONFIG ] ; then
      echo "mutex_set_max 10000000" > $RPM_CONFIG
      dockerrun "$CMSPKG rpmenv -- rpmdb --rebuilddb"
    fi
    # Since we are installing on a local disk, no need to worry about
    # the rpm database.
    #
    # Make sure we do not mess up environment.
    # Also we do not want the installation of one release (which can be broken)
    # to interfere with the installation of a different one. For that reason we
    # ignore the exit code.
    (
      dockerrun "${CMSPKG} update ; ${CMSPKG} -f install cms+cms-common+1.0 " ;
      REL_TO_INSTALL="" ;
      if [ "X$RELEASE_NAME" = "X" ] ; then 
        SEARCH="${CMSPKG} search cmssw-ib+CMSSW | cut -d'\' -f1 | sort > ${TMP_PREFIX}-onserver.txt ; \
        ${CMSPKG} rpm -- -qa --queryformat '%{NAME}\n' | grep cmssw-ib | sort > ${TMP_PREFIX}-installed.txt  " ;
        dockerrun $SEARCH ;
        REL_TO_INSTALL=`diff -u ${TMP_PREFIX}-onserver.txt ${TMP_PREFIX}-installed.txt | awk '{print $1}'| grep -e '^-[^-]' | sed -e 's/^-//'` ;
      else
        REL_TO_INSTALL="cms+cmssw-ib+$RELEASE_NAME" ;
      fi ;
      for x in $REL_TO_INSTALL; do
        INSTALL="${CMSPKG} install -y $x || true; \
        time ${CMSPKG} install -y `echo $x | sed -e 's/cmssw-ib/cmssw/'` || true; \
        time ${CMSPKG} install -y `echo $x | sed -e 's/cmssw-ib/cmssw-patch/'` || true; \
        ${CMSPKG} clean" ;
        dockerrun $INSTALL ;
        relname=`echo $x | awk -F + '{print $NF}'` ;
        timestamp=`echo $relname | awk -F _ '{print $NF}' | grep '^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]$' | sed 's|-||g'` ;
        if [ "X$timestamp" != "X" ] ; then
          for y in cmssw cmssw-patch ; do
            if [ -d $WORKDIR/$SCRAM_ARCH/cms/$y/$relname ] ; then
              touch -t $timestamp $WORKDIR/$SCRAM_ARCH/cms/$y/$relname ;
            fi
          done ;
        fi ;
        CURRENT_SIZE=`df -B 1M $DISK | grep /dev | awk {'print $3'}`
        if (( $CURRENT_SIZE - $INITIAL_SIZE > $PUBLISH_THRESHOLD )); then
          # If we already installed more than the threshold publish, put again the repository in transaction and reset INITIAL_SIZE
          echo "Threshold passed, forcing publishing."
          time cvmfs_server publish
          cvmfs_server transaction
          INITIAL_SIZE=`df -B 1M $DISK | grep /dev | awk {'print $3'}`
        fi
      done ;
      rm -f ${TMP_PREFIX}-installed.txt ;
      rm -f ${TMP_PREFIX}-onserver.txt
    ) || true

  done  #End architecture

done #End week repository

# Cleanup old weeks
find $BASEDIR/* -maxdepth 0 -type d -not \( -name "`echo $REPOSITORIES | awk '{print $1}'`" -or -name "`echo $REPOSITORIES | awk '{print $2}'`" \) | xargs rm -rf
# Remove all existing links for week[0-1]
for link in $(find $BASEDESTDIR/* -maxdepth 0 -type l); do unlink $link; done;
# Recreate links week[0-1]
for dir in $(find $BASEDESTDIR/* -maxdepth 0 -type d | grep -G "20[0-9][0-9]-[0-5][0-9]"); do ln -s $dir $( dirname $dir )/week$(( 10#$( echo $( basename $dir ) | cut -d"-" -f 2 )%2 )); done;
if [ -f $BASEDIR/week0/etc/scramrc/links.db ] ; then
 [ -s $BASEDIR/week0/etc/scramrc/links.db ] || echo $BASEDIR/week1 > $BASEDIR/week0/etc/scramrc/links.db
fi
if [ -f $BASEDIR/week1/etc/scramrc/links.db ] ; then
 [ -s $BASEDIR/week1/etc/scramrc/links.db ] || echo $BASEDIR/week0 > $BASEDIR/week1/etc/scramrc/links.db
fi


# Write everything in the repository
echo "Publishing started" `date`
time cvmfs_server publish

NEW_WEEKS=$(ls -d $BASEDIR/20*)
if [ "X${OLD_WEEKS}" != "X${NEW_WEEKS}" ] ; then
  echo "Running garbage collector"
  time cvmfs_server gc -f
fi

