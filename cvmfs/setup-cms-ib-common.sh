#!/bin/bash -ex
CMS_BOT_DIR=$(dirname $(realpath $0))/..
[ "${BASEDIR}" != "" ] || export BASEDIR=/cvmfs/$CVMFS_REPOSITORY
CVMFS_INSTALL=false
case ${BASEDIR} in
  /cvmfs/* ) CVMFS_INSTALL=true ;;
esac

siteconf=true
update=false
mkdir new_data
pushd new_data
if [ -e ${BASEDIR}/SITECONF/commit.id ] ; then
  SITECONF_SHA=$(curl -s https://api.github.com/repos/cms-sw/siteconf/branches/master | grep -A1  '"commit"' | grep '"sha"' | sed 's|.*: *"||;s|\".*||')
  [ "$(cat ${BASEDIR}/SITECONF/commit.id)" != "${SITECONF_SHA}" ] || siteconf=false
fi
if $siteconf ; then
  git clone --depth 1  https://github.com/cms-sw/siteconf.git SITECONF
  GIT_DIR=./SITECONF/.git git log -n 1 --pretty=format:"%H" > SITECONF/commit.id
  rm -rf ./SITECONF/.git
  update=true
fi
if [ ! -d  ${BASEDIR}/git ] ; then
  mkdir git
  update=true
fi
for w in $(tail -1 ${CMS_BOT_DIR}/ib-weeks | sed -e's/-\([0-9]\)$/-0\1/' | sort -r) ; do
  if [ ! -d ${BASEDIR}/$w ] ; then
    mkdir -p $w
    update=true
  fi
  for arch in x86_64 aarch64 ppc64le ; do
    if [ ! -d ${BASEDIR}/sw/$arch/$w ] ; then
      mkdir -p sw/$arch/$w
      update=true
    fi
  done
done
if [ -e ${CMS_BOT_DIR}/cvmfs/${CVMFS_REPOSITORY}/cvmfsdirtab.sh ] ; then
  CVMFS_DIR="${BASEDIR}" ${CMS_BOT_DIR}/cvmfs/${CVMFS_REPOSITORY}/cvmfsdirtab.sh  > .cvmfsdirtab
  if [ -e ${BASEDIR}/.cvmfsdirtab ] ; then
    if diff ${BASEDIR}/.cvmfsdirtab .cvmfsdirtab >/dev/null 2>&1 ; then
      rm -f .cvmfsdirtab
    fi
  fi
  [ ! -e .cvmfsdirtab ] || update=true
fi
popd
if $update ; then
  if $CVMFS_INSTALL ; then
    cvmfs_server transaction || ((cvmfs_server abort -f || rm -fR /var/spool/cvmfs/$CVMFS_REPOSITORY/is_publishing.lock) && cvmfs_server transaction)
  fi
  $siteconf && rm -rf ${BASEDIR}/SITECONF
  hostname > $BASEDIR/stratum0
  rsync -av new_data/ ${BASEDIR}/
  if $CVMFS_INSTALL ; then
    time cvmfs_server publish
  fi
fi
rm -rf new_data
