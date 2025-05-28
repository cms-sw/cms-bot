#!/bin/sh -ex

function install_package() {
  rm -f ${WORKSPACE}/inst.log
  ${CMSPKG} install -y $@ 2>&1 | tee -a ${WORKSPACE}/inst.log 2>&1 || true
  if [ $(grep 'cannot open Packages index using db6' ${WORKSPACE}/inst.log | wc -l) -gt 0 ] ; then
    if [ "${USE_LOCAL_RPMDB}" = "true" ] ; then
      rm -rf ${WORKSPACE}/rpm
      mv $WORKDIR/${SCRAM_ARCH}/var/lib/rpm  ${WORKSPACE}/rpm
      ln -d ${WORKSPACE}/rpm $WORKDIR/${SCRAM_ARCH}/var/lib/rpm
      rm -f ${WORKSPACE}/inst.log
      ${CMSPKG} install -y $@ 2>&1 | tee -a ${WORKSPACE}/inst.log 2>&1 || true
      rm -f $WORKDIR/${SCRAM_ARCH}/var/lib/rpm
      mv ${WORKSPACE}/rpm $WORKDIR/${SCRAM_ARCH}/var/lib/rpm
      if [ $(grep 'cannot open Packages index using db6' ${WORKSPACE}/inst.log | wc -l) -gt 0 ] ; then
        touch ${WORKSPACE}/err.txt
      fi
    else
      touch ${WORKSPACE}/err.txt
    fi
  fi
}

source $(dirname $0)/cmsrep.sh
CMS_BOT_DIR=$(dirname $(realpath $0))
source ${CMS_BOT_DIR}/cvmfs_deployment/utils.sh
CVMFS_INSTALL=false
[ "${BASEDIR}" != "" ] || BASEDIR="${CVMFS_BASEDIR}"
case ${BASEDIR} in
  /cvmfs/* ) CVMFS_INSTALL=true ;;
esac
${CVMFS_INSTALL}               || export USE_CVMFS_GW="false"
export BASEDIR
export THISDIR=$(/bin/pwd -P)
export LC_ALL=C
export LC_CTYPE=C
export LANG=C

ARCHITECTURE=$1
CMS_WEEK=$2
RELEASE_NAME=$3
WORKSPACE=$4
DEV=$5
PROOTDIR=$6
TEST_INSTALL=$7
NUM_WEEKS=$8
REINSTALL_ARGS=$9
INSTALL_PACKAGES="${10}"
USE_LOCAL_RPMDB="${11}"

CVMFS_PUBLISH_PATH=""
USE_DEV=""
export PROOTDIR
COMMON_BASEDIR="${BASEDIR}"
${CVMFS_INSTALL} && COMMON_BASEDIR="${CVMFS_BASEDIR}"
[ "$PROOTDIR" != "" ] || PROOTDIR=${CVMFS_BASEDIR}/proot
if ${USE_CVMFS_GW} ; then
  CMS_ARCH=$(echo ${ARCHITECTURE} | cut -d_ -f2)
  [ "${CMS_ARCH}" = "amd64" ] && CMS_ARCH="x86_64"
  CVMFS_PUBLISH_PATH="/sw/${CMS_ARCH}"
  export BASEDIR="${BASEDIR}${CVMFS_PUBLISH_PATH}"
fi
if [ "$REINSTALL_ARGS" = "true" ] ; then
  REINSTALL_ARGS="--reinstall"
else
  REINSTALL_ARGS=""
fi
[ "X$NUM_WEEKS" != "X" ] || NUM_WEEKS=2
if [ "X$DEV" = "Xtrue" ] ; then
  DEV="-dev"
  USE_DEV="--use-dev"
else
  DEV=""
fi

cd ${CMS_BOT_DIR}
[ -f ib-weeks ] || exit 1

# The repositories we need to install are those for which we find the
# timestamp files:
REPOSITORIES=`tail -${NUM_WEEKS} ib-weeks | sed -e's/-\([0-9]\)$/-0\1/' | sort -r`

echo $REPOSITORIES
$CVMFS_INSTALL && cvmfs_transaction ${CVMFS_PUBLISH_PATH}

hostname > $BASEDIR/stratum0

#Recreate the links
PUBLISH_CLEANUP=false
for link in $(find $BASEDIR -mindepth 1 -maxdepth 1 -name 'week*' -type l); do unlink $link; done
for t in nweek- ; do
  for w in $(find $BASEDIR -mindepth 1 -maxdepth 1 -name "$t*" -type d | sed 's|.*/||') ; do
    if [ $(echo "$REPOSITORIES" | grep "^$w$" | wc -l) -gt 0 ] ; then
      let N="$(echo $w | cut -d- -f2 | sed 's|^0||') % ${NUM_WEEKS}" || true
      ln -s $BASEDIR/$w $BASEDIR/week$N
    else
      echo "Deleting obsolete week $w"
      rm -rf $BASEDIR/$w
      $CVMFS_INSTALL && PUBLISH_CLEANUP=true
    fi
  done
done
if $PUBLISH_CLEANUP ; then
  time cvmfs_server publish
  cvmfs_transaction ${CVMFS_PUBLISH_PATH}
fi

# We install packages for both weeks. We reset every two week, alternating.
TMP_PREFIX=/tmp/cvsmfs-$$
export SCRAM_ARCH="$ARCHITECTURE"
export CMSPKG_OS_COMMAND="source ${CMS_BOT_DIR}/dockerrun.sh ; dockerrun"
for REPOSITORY in $REPOSITORIES; do
  echo $REPOSITORY
  let WEEK="$(echo $REPOSITORY | cut -d- -f2 | sed 's|^0*||') % ${NUM_WEEKS}" || true
  #If CMS_WEEK was set then only check releases for that week
  if [ "X$CMS_WEEK" != "X" -a "$CMS_WEEK" != "cms.week$WEEK" ] ; then
    echo "Skipping week for $REPOSITORY"
    continue
  fi
  echo "Checking week $REPOSITORY ($WEEK) for RPMS"
  if [ "X$TEST_INSTALL" = "XYes" ] ; then REPOSITORY="test" ; fi
  WORKDIR=$BASEDIR/$REPOSITORY
  rm -rf $WORKDIR/*/var/cmspkg/rpms || true
  mkdir -p $WORKDIR/logs
  # Install all architectures of the most recent week first.
    CMSPKG="$WORKDIR/common/cmspkg -a $SCRAM_ARCH ${USE_DEV}"
    LOGFILE=$WORKDIR/logs/bootstrap-$REPOSITORY-$SCRAM_ARCH.log
    #Recover from bad bootstrap arch
    if [ -f $LOGFILE -a ! -f $WORKDIR/$SCRAM_ARCH/cms/cms-common/1.0/etc/profile.d/init.sh ] ; then
      rm -f $LOGFILE
    fi
    # If the bootstrap log for the current week is not their rebootstrap the area.
    XPKGS="gcc-fixincludes"
    if [ ! -f $LOGFILE ]; then
      rm -rf $WORKDIR/$SCRAM_ARCH
      rm -rf $WORKDIR/bootstraptmp
      wget --tries=5 --waitretry=60 -O $WORKDIR/bootstrap.sh http://${CMSREP_IB_SERVER}/cmssw/repos/bootstrap${DEV}.sh
      rm -f ${LOGFILE}.err
      (source ${CMS_BOT_DIR}/dockerrun.sh ; export CMSPKG_OS_COMMAND="" ; dockerrun "sh -ex $WORKDIR/bootstrap.sh setup ${DEV} -server ${CMSREP_IB_SERVER} -path $WORKDIR -r cms.week$WEEK -arch $SCRAM_ARCH -y >$LOGFILE 2>&1" || touch ${LOGFILE}.err)
      if [ -e ${LOGFILE}.err ] ; then
        rm -f ${LOGFILE}.err
        cat ${LOGFILE}
        exit 1
      fi
      XPKGS="${XPKGS} SCRAMV1 SCRAMV2 cmssw-wm-tools cms-git-tools crab"
      [ "${RELEASE_NAME}" != "" ] || XPKGS="${XPKGS} cmssw-tool-conf"
    elif [ $(grep "server  *${CMSREP_IB_SERVER} " $WORKDIR/common/cmspkg | wc -l) -eq 0 ] ; then
      sed -i -e "s| \-\-server *[^ ]* | --server ${CMSREP_IB_SERVER} |" $WORKDIR/common/cmspkg
    fi
    #Ugrade cmspkg itself
    $CMSPKG -y upgrade
    #Upgrade any common packages e.g. cms-common, fakesystem etc.
    $CMSPKG -y --upgrade-packages upgrade
    for pkg in ${XPKGS} ; do
      INSTALL_PACKAGES="$(${CMSPKG} --build-order search +${pkg}+ | grep ${pkg} | sed 's| .*||' | head -1) ${INSTALL_PACKAGES}"
    done
    ln -sfT ${COMMON_BASEDIR}/SITECONF $WORKDIR/SITECONF
    if [ $(ls -rtd $WORKDIR/${SCRAM_ARCH}/external/rpm/4.* | tail -1 | sed 's|.*/external/rpm/4.||;s|\..*||') -lt 15 ] ; then
      RPM_CONFIG=$WORKDIR/${SCRAM_ARCH}/var/lib/rpm/DB_CONFIG
      if [ ! -e $RPM_CONFIG ] ; then
        echo "mutex_set_max 10000000" > $RPM_CONFIG
        $CMSPKG rpmenv -- rpmdb --rebuilddb
      fi
    fi
    (
      [ "${INSTALL_PACKAGES}" = "" ] || ${CMSPKG} -f install ${INSTALL_PACKAGES}
      if [ "X$RELEASE_NAME" != "X" ] ; then
        x="cms+cmssw-ib+$RELEASE_NAME"
        ${CMSPKG} clean
        install_package $x || true
        time install_package ${REINSTALL_ARGS} --ignore-size `echo $x | sed -e 's/cmssw-ib/cmssw/'`       || true
        time install_package ${REINSTALL_ARGS} --ignore-size `echo $x | sed -e 's/cmssw-ib/cmssw-patch/'` || true
        relname=`echo $x | awk -F + '{print $NF}'`
        timestamp=`echo $relname | awk -F _ '{print $NF}' | grep '^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]$' | sed 's|-||g'`
        if [ "X$timestamp" != "X" ] ; then
          for y in cmssw cmssw-patch ; do
            if [ -d $WORKDIR/$SCRAM_ARCH/cms/$y/$relname ] ; then
              touch -t $timestamp $WORKDIR/$SCRAM_ARCH/cms/$y/$relname
            fi
          done
        fi
      fi
    ) || true
if [ -e ${WORKSPACE}/err.txt ] ; then
  cvmfs_server abort -f
  exit 1
fi
rm -rf $WORKDIR/*/var/cmspkg/rpms || true
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
    let N="$(echo $w | cut -d- -f2 | sed 's|^0||') % ${NUM_WEEKS}" || true
    if [ $(echo "$REPOSITORIES" | grep "^$w$" | wc -l) -gt 0 ] ; then
      ln -s $BASEDIR/$w $BASEDIR/week$N
      [ -f $BASEDIR/week$N/etc/scramrc/links.db -a -s $BASEDIR/week$N/etc/scramrc/links.db ] && continue
      echo "$BASEDIR/scramdb" > $BASEDIR/week$N/etc/scramrc/links.db
    else
      echo "Deleting obsolete week $w"
      rm -rf $BASEDIR/$w
    fi
  done
done
rm -f $BASEDIR/latest
ln -s $(grep "^nweek-" ${CMS_BOT_DIR}/ib-weeks | tail -1) $BASEDIR/latest

if $CVMFS_INSTALL ; then
  # Write everything in the repository
  echo "Publishing started" `date`
  time cvmfs_server publish
fi
