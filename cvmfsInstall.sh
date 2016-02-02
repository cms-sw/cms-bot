#!/bin/sh -ex
ARCHITECTURE=$1
CMS_WEEK=$2
RELEASE_NAME=$3
export BASEDIR=/cvmfs/cms-ib.cern.ch
export BASEDESTDIR=/cvmfs/cms-ib.cern.ch
export THISDIR=`pwd`
export LANG=C
# The disk where cvmfs is mounted
export DISK="/dev/vdc"
export INITIAL_SIZE=`df -B 1M $DISK | grep /dev | awk {'print $3'}`
# Size in Mb to trigger publishing, this avoid huge publishing time (note at 3.6 Mb/s 13000 Mb is roughly 1 hr)
export PUBLISH_THRESHOLD=13000
# The repositories we need to install are those for which we find the
# timestamp files:
REPOSITORIES=`find /srv/cvmfs/shared/releases/ -type f | xargs -n1 basename | sed -e's/-\([0-9]\)$/-0\1/' | sort | tail -2 | sort -r`

echo $REPOSITORIES
ARCHITECTURES=$ARCHITECTURE
#If Architecture is not pass via command line then check for all ARCHS from the config.map file
if [ "X$ARCHITECTURE" = "X" ] ; then
  ARCHITECTURES=`curl -s https://raw.githubusercontent.com/cms-sw/cms-bot/HEAD/config.map | grep -o "slc[5-7]_amd64_gcc[0-9][0-9][0-9]" | sort -ur` #Reverse order to install most important IBs first
fi

echo $ARCHITECTURES
# Prepare the cvmfs repository in read/write mode
cvmfs_server transaction
# Check if the transaction really happened
if [ `touch $BASEDIR/is_writable 2> /dev/null; echo "$?"` -eq 0 ]; then
rm $BASEDIR/is_writable
else
echo CVMFS filesystem is not writable. Aborting.
echo " " | mail -s "cms-ib.cern.ch cannot be set to transaction" alessandro.degano@cern.ch
exit 1
fi

# Create Nested Catalogs file if it doesn't exist
if [ ! -f $BASEDIR/.cvmfsdirtab ]; then
cat <<EOF > $BASEDIR/.cvmfsdirtab
/*/*_*_*/external
/*/*_*_*/cms
/*/*_*_*/cms/cmssw
/*/*_*_*/cms/cmssw/*
/*/*_*_*/cms/cmssw-patch
/*/*_*_*/cms/cmssw-patch/*
/*/*_*_*/cms/cmssw-ib
/*/*_*_*/cms/cmssw-ib/*
EOF
fi

# Cleanup old weeks
find /cvmfs/cms-ib.cern.ch/* -maxdepth 0 -type d -not \( -name "`echo $REPOSITORIES | awk '{print $1}'`" -or -name "`echo $REPOSITORIES | awk '{print $2}'`" \) | xargs rm -rf
# Remove all existing links for week[0-1]
for link in $(find $BASEDESTDIR/* -maxdepth 0 -type l); do unlink $link; done;
# Recreate links week[0-1]
for dir in $(find $BASEDESTDIR/* -maxdepth 0 -type d | grep -G "20[0-9][0-9]-[0-5][0-9]"); do ln -s $dir $( dirname $dir )/week$(( 10#$( echo $( basename $dir ) | cut -d"-" -f 2 )%2 )); done;

dockerrun()
{
  if [ X$(echo $SCRAM_ARCH | cut -d"_" -f 1) == "Xslc7" ]; then
    ARGS="cd $THISDIR; $@"
    docker run -t -e THISDIR=${THISDIR} -e WORKDIR=${WORKDIR} -e SCRAM_ARCH=${SCRAM_ARCH} -e x=${x} -v ${WORKDIR}:${WORKDIR} -v ${THISDIR}:${THISDIR} -u $(whoami) cmssw/slc7-installer sh -c "$ARGS"
  else
    eval $@
  fi
}


# We install packages for both weeks. We reset every two week, alternating.
# Notice that the biweekly period for week 1 is shifted by 1 week for this
# reason we move it away from the 0 into 52 and take the modulo 52 afterward.
# Potentially we could separate the installation of the two volumes so that
# we don't need a huge local disk, but we can scatter this on different machienes.
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
    # Due to a bug in bootstrap.sh I need to install separate archs in separate directories.
    # This is because bootstraptmp is otherwise shared between different arches. Sigh.
    LOGFILE=$WORKDIR/bootstrap-$REPOSITORY-$SCRAM_ARCH.log
    # If the bootstrap log for the current two week period is not there
    # rebootstrap the area.
    if [ ! -f $LOGFILE ]; then
      # We move it so that if we are slow removing it, we do not endup removing
      # what got installed by someone else.
      mkdir -p $WORKDIR/common
      touch $LOGFILE
      wget -O $WORKDIR/bootstrap.sh http://cmsrep.cern.ch/cmssw/cms/bootstrap.sh
      dockerrun "sh -x $WORKDIR/bootstrap.sh setup -path $WORKDIR -r cms.week$WEEK -arch $SCRAM_ARCH -y >& $LOGFILE"
      echo /cvmfs/cms-ib.cern.ch/week`echo -e "0\n1" | grep -v $WEEK` > /cvmfs/cms-ib.cern.ch/week$WEEK/etc/scramrc/links.db
      APT_INSTALL="source $WORKDIR/$SCRAM_ARCH/external/apt/*/etc/profile.d/init.sh ; apt-get install -q -y cms+local-cern-siteconf+sm111124 || true"
      dockerrun $APT_INSTALL
    fi
    # Since we are installing on a local disk, no need to worry about
    # the rpm database.
    #
    # Make sure we do not mess up environment.
    # Also we do not want the installation of one release (which can be broken)
    # to interfere with the installation of a different one. For that reason we
    # ignore the exit code.
    (
      dockerrun "source $WORKDIR/$SCRAM_ARCH/external/apt/*/etc/profile.d/init.sh ; apt-get update " ;
      REL_TO_INSTALL="" ;
      if [ "X$RELEASE_NAME" = "X" ] ; then 
        APT_SEARCH="apt-cache search cmssw-ib\\\+CMSSW | cut -d'\' -f1 | sort > onserver.txt ; \
        rpm -qa --queryformat '%{NAME}\n' | grep cmssw-ib | sort > installed.txt  " ;
        dockerrun $APT_SEARCH ;
        REL_TO_INSTALL=`diff -u onserver.txt installed.txt | awk '{print $1}'| grep -e '^-[^-]' | sed -e 's/^-//'` ;
      else
        REL_TO_INSTALL="cms+cmssw-ib+$RELEASE_NAME" ;
      fi ;
      for x in $REL_TO_INSTALL; do
        APT_INSTALL="source $WORKDIR/$SCRAM_ARCH/external/apt/*/etc/profile.d/init.sh ; \
        apt-get install -q -y $x || true; \
        apt-get install -q -y `echo $x | sed -e 's/cmssw-ib/cmssw/'` || true; \
        apt-get install -q -y `echo $x | sed -e 's/cmssw-ib/cmssw-patch/'` || true" ;
        dockerrun $APT_INSTALL ;
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
          cvmfs_server publish
          cvmfs_server transaction
          INITIAL_SIZE=`df -B 1M $DISK | grep /dev | awk {'print $3'}`
        fi
      done ;
      rm -f installed.txt ;
      rm -f onserver.txt ;
      dockerrun "source $WORKDIR/$SCRAM_ARCH/external/apt/*/etc/profile.d/init.sh ; apt-get clean"
    ) || true

  done  #End architecture

done #End week repository

# Cleanup old weeks
find /cvmfs/cms-ib.cern.ch/* -maxdepth 0 -type d -not \( -name "`echo $REPOSITORIES | awk '{print $1}'`" -or -name "`echo $REPOSITORIES | awk '{print $2}'`" \) | xargs rm -rf
# Remove all existing links for week[0-1]
for link in $(find $BASEDESTDIR/* -maxdepth 0 -type l); do unlink $link; done;
# Recreate links week[0-1]
for dir in $(find $BASEDESTDIR/* -maxdepth 0 -type d | grep -G "20[0-9][0-9]-[0-5][0-9]"); do ln -s $dir $( dirname $dir )/week$(( 10#$( echo $( basename $dir ) | cut -d"-" -f 2 )%2 )); done;

# Write everything in the repository
echo "Publishing started" `date`
time cvmfs_server publish

