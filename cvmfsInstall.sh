#!/bin/sh -ex
source $(dirname $0)/dockerrun.sh
source $(dirname $0)/cmsrep.sh
CMS_BOT_DIR=$(dirname $(realpath $0))
export BASEDIR=/cvmfs/$CVMFS_REPOSITORY
export THISDIR=$(/bin/pwd -P)
export LC_ALL=C
export LC_CTYPE=C
export LANG=C

ARCHITECTURE=$1
CMS_WEEK=$2
RELEASE_NAME=$3
WORKSPACE=$4
DEV=$5
USE_DEV=""
PROOTDIR=$6
TEST_INSTALL=$7
NUM_WEEKS=$8
REINSTALL_COMMON=$9
INSTALL_PACKAGES="${10}"
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

if [ "X$PROOTDIR" = "X" ] ; then
  PROOTDIR=${BASEDIR}/proot
fi

cd $WORKSPACE/cms-bot
[ -f ib-weeks ] || exit 1

# The repositories we need to install are those for which we find the
# timestamp files:
REPOSITORIES=`tail -${NUM_WEEKS} ib-weeks | sed -e's/-\([0-9]\)$/-0\1/' | sort -r`

echo $REPOSITORIES
# Prepare the cvmfs repository in read/write mode
cvmfs_server transaction || ((cvmfs_server abort -f || rm -fR /var/spool/cvmfs/$CVMFS_REPOSITORY/is_publishing.lock) && cvmfs_server transaction)
# Check if the transaction really happened
if [ `touch $BASEDIR/is_writable 2> /dev/null; echo "$?"` -eq 0 ]; then
  rm $BASEDIR/is_writable
else
  echo CVMFS filesystem is not writable. Aborting.
  echo " " | mail -s "$CVMFS_REPOSITORY cannot be set to transaction" cms-sdt-logs@cern.ch
  exit 1
fi

export PROOTDIR
if [ $(echo $PROOTDIR | grep $BASEDIR | wc -l) -gt 0 ] ; then
  [ -d $PROOTDIR ] || mkdir -p $PROOTDIR
  PROOT_URL="https://cmssdt.cern.ch/SDT/proot/"
  for x in proot qemu-aarch64 qemu-ppc64le ; do
    if [ ! -x $PROOTDIR/$x ] ; then
      rm -rf $PROOTDIR/$x
      wget -q -O $PROOTDIR/$x "${PROOT_URL}/${x}"
      chmod +x $PROOTDIR/$x
    fi
  done
fi

hostname > $BASEDIR/stratum0
if [ -d $BASEDIR/SITECONF ] ; then
  pushd $BASEDIR/SITECONF
    git pull --rebase || true
  popd
else
  git clone https://github.com/cms-sw/siteconf.git $BASEDIR/SITECONF
fi

# Create Nested Catalogs file
if [ -e $WORKSPACE/cms-bot/cvmfs/${CVMFS_REPOSITORY}/cvmfsdirtab.sh ] ; then
  $WORKSPACE/cms-bot/cvmfs/${CVMFS_REPOSITORY}/cvmfsdirtab.sh  > $BASEDIR/.cvmfsdirtab
elif [ -f $WORKSPACE/cms-bot/cvmfs/${CVMFS_REPOSITORY}/cvmfsdirtab ] ; then
  cp -f $WORKSPACE/cms-bot/cvmfs/${CVMFS_REPOSITORY}/cvmfsdirtab $BASEDIR/.cvmfsdirtab
fi

#Recreate the links
for link in $(find $BASEDIR -mindepth 1 -maxdepth 1 -name 'week*' -type l); do unlink $link; done
for t in nweek- ; do
  for w in $(find $BASEDIR -mindepth 1 -maxdepth 1 -name "$t*" -type d | sed 's|.*/||') ; do
    if [ $(echo "$REPOSITORIES" | grep "^$w$" | wc -l) -gt 0 ] ; then
      let N="$(echo $w | cut -d- -f2) % ${NUM_WEEKS}" || true
      ln -s $BASEDIR/$w $BASEDIR/week$N
    else
      echo "Deleting obsolete week $w"
      rm -rf $BASEDIR/$w
    fi
  done
done

# We install packages for both weeks. We reset every two week, alternating.
TMP_PREFIX=/tmp/cvsmfs-$$
export SCRAM_ARCH="$ARCHITECTURE"
export CMSPKG_OS_COMMAND="source ${CMS_BOT_DIR}/dockerrun.sh ; dockerrun"
for REPOSITORY in $REPOSITORIES; do
  echo $REPOSITORY
  let WEEK="$(echo $REPOSITORY | cut -d- -f2) % ${NUM_WEEKS}" || true
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
    CMSPKG="$WORKDIR/common/cmspkg -a $SCRAM_ARCH ${USE_DEV}"
    LOGFILE=$WORKDIR/logs/bootstrap-$REPOSITORY-$SCRAM_ARCH.log
    #Recover from bad bootstrap arch
    if [ -f $LOGFILE -a ! -f $WORKDIR/$SCRAM_ARCH/cms/cms-common/1.0/etc/profile.d/init.sh ] ; then
      rm -f $LOGFILE
    fi
    # If the bootstrap log for the current week is not their rebootstrap the area.
    if [ ! -f $LOGFILE ]; then
      rm -rf $WORKDIR/$SCRAM_ARCH
      rm -rf $WORKDIR/bootstraptmp
      wget --tries=5 --waitretry=60 -O $WORKDIR/bootstrap.sh http://${CMSREP_IB_SERVER}/cmssw/repos/bootstrap${DEV}.sh
      dockerrun "sh -ex $WORKDIR/bootstrap.sh setup ${DEV} -server ${CMSREP_IB_SERVER} -path $WORKDIR -r cms.week$WEEK -arch $SCRAM_ARCH -y >& $LOGFILE" || (cat $LOGFILE && exit 1)
      if [ "${INSTALL_PACKAGES}" = "" ] ; then
        INSTALL_PACKAGES=$(${CMSPKG} search SCRAMV1 | sed 's| .*||' | grep 'SCRAMV1' | sort | tail -1)
      fi
    elif [ $(grep "server  *${CMSREP_IB_SERVER} " $WORKDIR/common/cmspkg | wc -l) -eq 0 ] ; then
      sed -i -e "s| \-\-server *[^ ]* | --server ${CMSREP_IB_SERVER} |" $WORKDIR/common/cmspkg
    fi
    INSTALL_PACKAGES="$(${CMSPKG} search gcc-fixincludes | sed 's| .*||' | grep 'gcc-fixincludes' | sort | tail -1) ${INSTALL_PACKAGES}"
    ln -sfT ../SITECONF $WORKDIR/SITECONF
    $CMSPKG -y upgrade
    if [ $(ls -rtd $WORKDIR/${SCRAM_ARCH}/external/rpm/4.* | tail -1 | sed 's|.*/external/rpm/4.||;s|\..*||') -lt 15 ] ; then
      RPM_CONFIG=$WORKDIR/${SCRAM_ARCH}/var/lib/rpm/DB_CONFIG
      if [ ! -e $RPM_CONFIG ] ; then
        echo "mutex_set_max 10000000" > $RPM_CONFIG
        $CMSPKG rpmenv -- rpmdb --rebuilddb
      fi
    fi
    (
      ${CMSPKG} update ; ${CMSPKG} -f $REINSTALL_COMMON install cms+cms-common+1.0 ${INSTALL_PACKAGES} ;
      if [ "X$RELEASE_NAME" != "X" ] ; then
        x="cms+cmssw-ib+$RELEASE_NAME" ;
        ${CMSPKG} clean ;
        ${CMSPKG} install -y $x || true;
        time ${CMSPKG} install -y `echo $x | sed -e 's/cmssw-ib/cmssw/'` || true;
        time ${CMSPKG} install -y `echo $x | sed -e 's/cmssw-ib/cmssw-patch/'` || true;
        relname=`echo $x | awk -F + '{print $NF}'` ;
        timestamp=`echo $relname | awk -F _ '{print $NF}' | grep '^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]$' | sed 's|-||g'` ;
        if [ "X$timestamp" != "X" ] ; then
          for y in cmssw cmssw-patch ; do
            if [ -d $WORKDIR/$SCRAM_ARCH/cms/$y/$relname ] ; then
              touch -t $timestamp $WORKDIR/$SCRAM_ARCH/cms/$y/$relname ;
            fi
          done ;
        fi ;
      fi
    ) || true
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
    let N="$(echo $w | cut -d- -f2) % ${NUM_WEEKS}" || true
    if [ $(echo "$REPOSITORIES" | grep "^$w$" | wc -l) -gt 0 ] ; then
      ln -s $BASEDIR/$w $BASEDIR/week$N
      [ -f $BASEDIR/week$N/etc/scramrc/links.db ] || continue
      echo "$BASEDIR/scramdb" > $BASEDIR/week$N/etc/scramrc/links.db
    else
      echo "Deleting obsolete week $w"
      rm -rf $BASEDIR/$w
    fi
  done
done
rm -f $BASEDIR/latest
ln -s $(grep "^nweek-" $WORKSPACE/cms-bot/ib-weeks | tail -1) $BASEDIR/latest

# Write everything in the repository
echo "Publishing started" `date`
time cvmfs_server publish
