#!/bin/sh -ex
source $(dirname $0)/dockerrun.sh
ARCHITECTURE=$1
CMS_WEEK=$2
RELEASE_NAME=$3
WORKSPACE=$4
DEV=$5
USE_DEV=""
TEST_INSTALL=$7
NUM_WEEKS=$8
REINSTALL_COMMON=$9
if [ "$REINSTALL_COMMON" = "true" ] ; then
  REINSTALL_COMMON="--reinstall"
else
  REINSTALL_COMMON=""
fi
if [ "X$NUM_WEEKS" = "X" ] ; then NUM_WEEKS=2; fi
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
[ -d $PROOTDIR ] || mkdir -p $PROOTDIR
PROOT_URL="https://cmssdt.cern.ch/SDT/proot/"
for x in proot qemu-aarch64 qemu-ppc64le ; do
  if [ ! -x $PROOTDIR/$x ] ; then
    rm -rf $PROOTDIR/$x
    wget -q -O $PROOTDIR/$x "${PROOT_URL}/${x}"
    chmod +x $PROOTDIR/$x
  fi
done

cd $WORKSPACE/cms-bot
[ -f ib-weeks ] || exit 1

export CMSIB_CVMFS_REPO=cms-ib.cern.ch
export BASEDIR=/cvmfs/$CMSIB_CVMFS_REPO
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
# The repositories we need to install are those for which we find the
# timestamp files:
REPOSITORIES=`tail -${NUM_WEEKS} ib-weeks | sed -e's/-\([0-9]\)$/-0\1/' | sort -r`

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
export INITIAL_SIZE=`df -B 1M $DISK | awk '{print $3}' | tail -1`
# Size in Mb to trigger publishing, this avoid huge publishing time (note at 3.6 Mb/s 13000 Mb is roughly 1 hr)
export PUBLISH_THRESHOLD=13000
hostname > $BASEDIR/stratum0
if [ -d $BASEDIR/SITECONF ] ; then
  pushd $BASEDIR/SITECONF
    git pull --rebase || true
  popd
else
  git clone https://github.com/cms-sw/siteconf.git $BASEDIR/SITECONF
fi

# Create Nested Catalogs file
cp -f $WORKSPACE/cms-bot/cvmfsdirtab $BASEDIR/.cvmfsdirtab

#Recreate the links
for link in $(find $BASEDIR -mindepth 1 -maxdepth 1 -name 'week*' -type l); do unlink $link; done
for t in nweek- ; do
  for w in $(find $BASEDIR -mindepth 1 -maxdepth 1 -name "$t*" -type d | sed 's|.*/||') ; do
    if [ $(echo "$REPOSITORIES" | grep "^$w$" | wc -l) -gt 0 ] ; then
      N=$(echo "$(echo $w | cut -d- -f2) % ${NUM_WEEKS}" | bc)
      ln -s $BASEDIR/$w $BASEDIR/week$N
    else
      echo "Deleting obsolete week $w"
      echo rm -rf $BASEDIR/$w
    fi
  done
done

# We install packages for both weeks. We reset every two week, alternating.
# Notice that the biweekly period for week 1 is shifted by 1 week for this
# reason we move it away from the 0 into 52 and take the modulo 52 afterward.
# Potentially we could separate the installation of the two volumes so that
# we don't need a huge local disk, but we can scatter this on different machienes.
TMP_PREFIX=/tmp/cvsmfs-$$
for REPOSITORY in $REPOSITORIES; do
  echo $REPOSITORY
  WEEK=$(echo "$(echo $REPOSITORY | cut -d- -f2) % ${NUM_WEEKS}" | bc)
  #If CMS_WEEK was set then only check releases for that week
  if [ "X$CMS_WEEK" != "X" -a "$CMS_WEEK" != "cms.week$WEEK" ] ; then
    echo "Skipping week for $REPOSITORY"
    continue
  fi
  echo "Checking week $REPOSITORY ($WEEK) for RPMS"
  if [ "X$TEST_INSTALL" = "XYes" ] ; then REPOSITORY="test" ; fi
  WORKDIR=$BASEDIR/$REPOSITORY
  mkdir -p $WORKDIR/logs
  # Install all architectures of the most recent week first.
  for SCRAM_ARCH in $ARCHITECTURES; do
    CMSPKG="$WORKDIR/common/cmspkg -a $SCRAM_ARCH ${USE_DEV}"
    # Due to a bug in bootstrap.sh I need to install separate archs in separate directories.
    # This is because bootstraptmp is otherwise shared between different arches. Sigh.
    LOGFILE=$WORKDIR/logs/bootstrap-$REPOSITORY-$SCRAM_ARCH.log
    #Recover from bad bootstrap arch
    if [ -f $LOGFILE -a ! -f $WORKDIR/$SCRAM_ARCH/cms/cms-common/1.0/etc/profile.d/init.sh ] ; then
      rm -f $LOGFILE
    fi
    # If the bootstrap log for the current two week period is not there
    # rebootstrap the area.
    if [ ! -f $LOGFILE ]; then
      rm -rf $WORKDIR/$SCRAM_ARCH
      rm -rf $WORKDIR/bootstraptmp
      wget --tries=5 --waitretry=60 -O $WORKDIR/bootstrap.sh http://cmsrep.cern.ch/cmssw/repos/bootstrap${DEV}.sh
      dockerrun "sh -ex $WORKDIR/bootstrap.sh setup ${DEV} -path $WORKDIR -r cms.week$WEEK -arch $SCRAM_ARCH -y >& $LOGFILE" || (cat $LOGFILE && exit 1)
      SCRAM_PKG=$(${CMSPKG} search SCRAMV1 | sed 's| .*||' | grep 'SCRAMV1' | sort | tail -1)
      if [ "X${SCRAM_PKG}" != "X" ] ; then dockerrun "${CMSPKG} -f install ${SCRAM_PKG}" || true ; fi
    fi
    ln -sfT ../SITECONF $WORKDIR/SITECONF
    $CMSPKG -y upgrade
    if [ $(echo "${SCRAM_ARCH}" | grep '^cc' | wc -l) -eq 0 ] ; then
      RPM_CONFIG=$WORKDIR/${SCRAM_ARCH}/var/lib/rpm/DB_CONFIG
      if [ ! -e $RPM_CONFIG ] ; then
        echo "mutex_set_max 10000000" > $RPM_CONFIG
        dockerrun "$CMSPKG rpmenv -- rpmdb --rebuilddb"
      fi
    fi
    # Since we are installing on a local disk, no need to worry about
    # the rpm database.
    #
    # Make sure we do not mess up environment.
    # Also we do not want the installation of one release (which can be broken)
    # to interfere with the installation of a different one. For that reason we
    # ignore the exit code.
    (
      dockerrun "${CMSPKG} update ; ${CMSPKG} -f $REINSTALL_COMMON install cms+cms-common+1.0 " ;
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
        CURRENT_SIZE=`df -B 1M $DISK | awk '{print $3}' | tail -1`
        if (( $CURRENT_SIZE - $INITIAL_SIZE > $PUBLISH_THRESHOLD )); then
          # If we already installed more than the threshold publish, put again the repository in transaction and reset INITIAL_SIZE
          echo "Threshold passed, forcing publishing."
          time cvmfs_server publish
          cvmfs_server transaction
          INITIAL_SIZE=`df -B 1M $DISK | awk '{print $3}' | tail -1`
        fi
      done ;
      rm -f ${TMP_PREFIX}-installed.txt ;
      rm -f ${TMP_PREFIX}-onserver.txt
    ) || true

  done  #End architecture

done #End week repository

mkdir -p $BASEDIR/scramdb/etc/scramrc
rm -f $BASEDIR/scramdb/etc/scramrc/links.db
touch $BASEDIR/scramdb/etc/scramrc/links.db
for (( i=0; i<$NUM_WEEKS; i++ )) ; do
 echo "$BASEDIR/week$i" >> $BASEDIR/scramdb/etc/scramrc/links.db
done
echo "/cvmfs/cms.cern.ch" >> $BASEDIR/scramdb/etc/scramrc/links.db

#Recreate the links
for link in $(find $BASEDIR -mindepth 1 -maxdepth 1 -name 'week*' -type l); do unlink $link; done
for t in nweek- ; do
  for w in $(find $BASEDIR -mindepth 1 -maxdepth 1 -name "$t*" -type d | sed 's|.*/||') ; do
    N=$(echo "$(echo $w | cut -d- -f2) % ${NUM_WEEKS}" | bc)
    if [ $(echo "$REPOSITORIES" | grep "^$w$" | wc -l) -gt 0 ] ; then
      ln -s $BASEDIR/$w $BASEDIR/week$N
      [ -f $BASEDIR/week$N/etc/scramrc/links.db ] || continue
      echo "$BASEDIR/scramdb" > $BASEDIR/week$N/etc/scramrc/links.db
    else
      echo "Deleting obsolete week $w"
      echo rm -rf $BASEDIR/$w
    fi
  done
done

# Write everything in the repository
echo "Publishing started" `date`
time cvmfs_server publish

