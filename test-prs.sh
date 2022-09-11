#!/bin/bash -ex
export WORKSPACE=$(/bin/pwd -P)
export KEEP_SOURCE_GIT=true
export BUILD_DIR=externals
source $(dirname $0)/cmsrep.sh
ARCH=""
CMSDIST_BR=""
PRS=""
RELEASE_QUEUE=""
while [ "$#" != 0 ]; do
  case "$1" in
    -h|--help)
      echo "Usage: $0 [-c|--cmsdist branch] [-a|--architecture architecture] repo#PR [repo#PR]"
      exit 0
      ;;
    -c|--cmsdist)
      CMSDIST_BR=$2 ; shift ; shift
      ;;
    -a|--architecture)
      ARCH=$2 ; shift ; shift
      ;;
    -r|--release)
      RELEASE_QUEUE=$2 ; shift ; shift
      ;;
    *)
      PRS="$PRS $(echo $1 | tr ',' ' ')" ; shift
      ;;
  esac
done

if [ "$PRS" == "" ] ; then
  echo "Usage: $0 [-c|--cmsdist branch] [-a|--architecture architecture] repo#PR [repo#PR]"
  exit 1
fi

CMS_BOT_DIR=$(cd $(dirname $0); /bin/pwd -P)
COMMON=${CMS_BOT_DIR}/common
source ${CMS_BOT_DIR}/pr_testing/_helper_functions.sh
let NCPU=$(${COMMON}/get_cpu_number.sh)/2

#Clone and merge PRs
for PR in $(echo $PRS | tr ' ' '\n' | grep -v '/cmssw#') ; do
  REPO=$(echo ${PR} | sed 's|#.*||;s|.*/||')
  echo "Cloning ${REPO} and merging ${PR}"
  git_clone_and_merge $(get_cached_GH_JSON ${PR}) </dev/null
  if [ "$CMSDIST_BR" = "" -a $(echo "$PR" | grep "/cmsdist#" | wc -l) -gt 0 ] ; then
    CMSDIST_BR=$(get_base_branch ${PR})
  fi
done

#Find CMSSW configuration
CONFIG_LINE=$(${COMMON}/get_config_map_line.sh "${RELEASE_QUEUE}" "${CMSDIST_BR}" "${ARCH}")
if [ "$CONFIG_LINE" = "" ] ; then
  echo "ERROR: Unable to find configuration for cmsdist branch ${CMSDIST_BR} in ${CMS_BOT_DIR}/config.map"
  exit 1
fi

#Checkout cmsdist and pkgtools if not already dne via PRs
if [ ! -e cmsdist ] ; then
  CMSDIST_BR=$(echo ${CONFIG_LINE} | sed 's/^.*CMSDIST_TAG=//' | sed 's/;.*//' )
  echo "Cloning cmsdist tag ${CMSDIST_BR}"
  git clone --depth 1 -b $CMSDIST_BR git@github.com:cms-sw/cmsdist
fi

if [ ! -e pkgtools ] ; then
  PKGTOOLS_BR=$(echo ${CONFIG_LINE} | sed 's/^.*PKGTOOLS_TAG=//' | sed 's/;.*//' )
  echo "Cloning pkgtools tag ${PKGTOOLS_BR}"
  git clone --depth 1 -b $PKGTOOLS_BR git@github.com:cms-sw/pkgtools
fi

#Set SCRAM_ARCH and CMSSW_QUEUE
export SCRAM_ARCH=$(echo ${CONFIG_LINE} | sed 's/^.*SCRAM_ARCH=//' | sed 's/;.*//' )
export CMSSW_QUEUE=$(echo ${CONFIG_LINE} | sed 's/^.*RELEASE_QUEUE=//' | sed 's/;.*//' )

#Download external tools sources to be used to build any externals
for PKG_REPO in $(echo $PRS | tr ' ' '\n' | sed 's|#.*||' | sort | uniq) ; do
  PKG_NAME=$(echo ${PKG_REPO} | sed 's|.*/||')
  case "$PKG_NAME" in
    cmsdist|pkgtools|cms-bot|cmssw ) ;;
    * )
      echo "Finding sources for ${PKG_REPO}"
      SPEC_NAME=$(${CMS_BOT_DIR}/pr_testing/get_external_name.sh ${PKG_REPO})
      ${CMS_BOT_DIR}/pr_testing/get_source_flag_for_cmsbuild.sh "$PKG_REPO" "$SPEC_NAME" "$CMSSW_QUEUE" "$SCRAM_ARCH" "" "${BUILD_DIR}"
      echo "Sources: $(tail -1 ${WORKSPACE}/get_source_flag_result.txt)"
      ;;
  esac
done

#Get cmsBuild --source flag value if any
SOURCE_FLAG=
if [ -e get_source_flag_result.txt ] ; then
  SOURCE_FLAG=$(cat get_source_flag_result.txt | sort | uniq)
fi

#Build externals
COMPILATION_CMD="PYTHONPATH= ./pkgtools/cmsBuild --server http://${CMSREP_IB_SERVER}/cgi-bin/cmspkg --upload-server ${CMSREP_IB_SERVER} -i ${BUILD_DIR} ${SOURCE_FLAG} --arch $SCRAM_ARCH -j ${NCPU}"
if [ ${PKG_TOOL_VERSION} -gt 31 ] ; then
  COMPILATION_CMD="${COMPILATION_CMD} --force-tag --tag hash --delete-build-directory --link-parent-repository --weekly"
else
  let CMS_WEEK_NUM="(($(date -d "$(date +%m/%d/%Y) 00:00:00z" +%s)/86400)+4)/7"
  CMS_WEEK_NUM=$(echo 00000${CMS_WEEK_NUM} | sed 's|^.*\(.....\)$|\1|;s|0*||')
  let CMS_REPOSITORY=${CMS_WEEK_NUM}%2 || true
  CMS_REPOSITORY="cms.week${CMS_REPOSITORY}"
  COMPILATION_CMD="${COMPILATION_CMD} --repo ${CMS_REPOSITORY}"
fi
COMPILATION_CMD="${COMPILATION_CMD} build cmssw-tool-conf"

echo "${COMPILATION_CMD}"
[ -e $WORKSPACE/cmsswtoolconf.log ] && mv $WORKSPACE/cmsswtoolconf.log $WORKSPACE/cmsswtoolconf.log.$(date +%s)
eval $COMPILATION_CMD 2>&1 | tee $WORKSPACE/cmsswtoolconf.log
TOOL_CONF_VER=$(ls -d $WORKSPACE/${BUILD_DIR}/${SCRAM_ARCH}/cms/cmssw-tool-conf/* | sed 's|.*/||')

source $WORKSPACE/${BUILD_DIR}/cmsset_default.sh
echo /cvmfs/cms.cern.ch > $WORKSPACE/${BUILD_DIR}/etc/scramrc/links.db

#Find CMSSW IB to use to test externals
CMSSW_IB=$(scram -a $SCRAM_ARCH l -c $CMSSW_QUEUE | grep -v -f "${CMS_BOT_DIR}/ignore-releases-for-tests" | awk '{print $2}' | sort -r | head -1)
if [ ! -d ${CMSSW_IB} ] ; then
  echo "Setting up ${CMSSW_IB} area...."
  scram -a $SCRAM_ARCH project ${CMSSW_IB}
fi

cd ${CMSSW_IB}
ls $WORKSPACE/${BUILD_DIR}/share/lcg/SCRAMV1 > config/scram_version
rm -f config/scram_basedir

config_tag=$(grep '%define *configtag *V' $WORKSPACE/cmsdist/scram-project-build.file | sed 's|.*configtag *V|V|;s| *||g')
if [ "$(cat config/config_tag)" != "${config_tag}" ] ; then
  git clone git@github.com:cms-sw/cmssw-config scram-buildrules
  pushd scram-buildrules
    git checkout ${config_tag}
    echo ${config_tag} > ../config/config_tag
  popd
  mv config/SCRAM config/SCRAM.orig
  cp -r scram-buildrules/SCRAM config/SCRAM
  if [ -d scram-buildrules/Projects/CMSSW ] ; then
    cp -f scram-buildrules/Projects/CMSSW/BuildFile.xml config/BuildFile.xml
    cp -f scram-buildrules/Projects/CMSSW/SCRAM_ExtraBuildRule.pm config/SCRAM_ExtraBuildRule.pm
  else
    cp -f scram-buildrules/CMSSW_BuildFile.xml config/BuildFile.xml
    cp -f scram-buildrules/CMSSW_SCRAM_ExtraBuildRule.pm config/SCRAM_ExtraBuildRule.pm
  fi
  if [ -f config/SCRAM.orig/GMake/CXXModules.mk ] ; then
    cp $WORKSPACE/cmsdist/CXXModules.mk.file config/SCRAM/GMake/CXXModules.mk
    if [ "X${CLING_PREBUILT_MODULE_PATH}" = "X" ] ; then
      export CLING_PREBUILT_MODULE_PATH="${WORKSPACE}/${CMSSW_IB}/lib/${SCRAM_ARCH}"
    fi
  fi
  rm -rf scram-buildrules
fi

#Setup newly build tools
CONF="config/toolbox/${SCRAM_ARCH}/tools/selected"
CONF_BACK="config/toolbox/${SCRAM_ARCH}/tools/selected.backup"
if [ ! -d ${CONF_BACK} ] ; then mv ${CONF} ${CONF_BACK} ; fi
rm -rf ${CONF}
TOOL_CONF="$WORKSPACE/$BUILD_DIR/$SCRAM_ARCH/cms/cmssw-tool-conf/${TOOL_CONF_VER}/tools/selected"
rsync -a ${TOOL_CONF}/ ${CONF}/
if [ -e "${CONF_BACK}/cmssw.xml" ] ; then cp ${CONF_BACK}/cmssw.xml ${CONF}/cmssw.xml ; fi
RMV_CMSSW_EXTERNAL="$(ls -d config/SCRAM/hooks/runtime/*-remove-release-external-lib 2>/dev/null || true)"
if [ "${RMV_CMSSW_EXTERNAL}" != "" ] ; then chmod +x ${RMV_CMSSW_EXTERNAL} ; fi
echo "Setting up newly build tools"
DEP_NAMES=
for xml in $(ls ${CONF}/*.xml) ; do
  name=$(basename $xml)
  tool=$(echo $name | sed 's|.xml$||')
  if [ ! -e ${CONF_BACK}/$name ] ; then
    echo "Setting up new tool $name..."
    scram setup $xml
    continue
  fi
  nver=$(grep '<tool ' $xml               | tr ' ' '\n' | grep 'version=' | sed 's|version="||;s|".*||g')
  over=$(grep '<tool ' ${CONF_BACK}/$name | tr ' ' '\n' | grep 'version=' | sed 's|version="||;s|".*||g')
  if [ "$nver" = "$over" ] ; then continue ; fi
  echo "Settings up $name: $over vs $nver"
  DEP_NAMES="$DEP_NAMES echo_${tool}_USED_BY"
done

#Setup new tools
touch ${CONF}/*.xml
scram setup
scram setup self
rm -rf external
scram b echo_CXX >/dev/null 2>&1
eval `scram run -sh`

#Find and checkout CMSSW packages which needs to be rebuild
CMSSW_DEP=$(scram build ${DEP_NAMES} | tr ' ' '\n' | grep '^cmssw/\|^self/' | cut -d"/" -f 2,3 | sort | uniq)
if [ "X${CMSSW_DEP}" != "X" ] ; then
  git cms-addpkg --ssh $CMSSW_DEP
fi

#Checkout any CMSSW PRs
for PR in $(echo $PRS | tr ' ' '\n' | grep '/cmssw#' | sed 's|/cmssw#|:|') ; do
  git cms-merge-topic --ssh -u $PR
done
echo "Please go to $CMSSW_BASE and checkout any extra CMSSW packages and rebuild."
