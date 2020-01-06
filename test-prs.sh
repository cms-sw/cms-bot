#!/bin/bash -e
export WORKSPACE=$(/bin/pwd)
export KEEP_SOURCE_GIT=true
export BUILD_DIR=externals
if [ "$@" == "" ] ; then
  echo "Usage: $0 repo#PR repo/PR"
  exit 1
fi

CMS_BOT_DIR=$(cd $(dirname $0); /bin/pwd -P)
COMMON=${CMS_BOT_DIR}/common
export WORPSPACE=$(/bin/pwd -P)
source ${CMS_BOT_DIR}/pr_testing/_helper_functions.sh
let NCPU=$(${COMMON}/get_cpu_number.sh)/2

#Clone and merge PRs
CMSDIST_BR=""
for PR in $(echo $@ | tr ' ' '\n' | grep -v '/cmssw#') ; do
  REPO=$(echo ${PR} | sed 's|#.*||;s|.*/||')
  if [ ! -e ${REPO} ] ; then
    echo "Cloning ${REPO} and merging ${PR}"
    git_clone_and_merge $(get_cached_GH_JSON ${PR}) </dev/null
  fi
  if [ "$CMSDIST_BR" = "" -a $(echo "$PR" | grep "/cmsdist#" | wc -l) -gt 0 ] ; then
    CMSDIST_BR=$(get_base_branch ${PR})
  fi
done

#Find CMSSW configuration
CONFIG_LINE=$(${COMMON}/get_config_map_line.sh "" "$CMSDIST_BR" "")
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
for PKG_REPO in $(echo $@ | tr ' ' '\n' | sed 's|#.*||' | sort | uniq) ; do
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
COMPILATION_CMD="PYTHONPATH= ./pkgtools/cmsBuild --weekly -i ${BUILD_DIR} ${SOURCE_FLAG} --arch $SCRAM_ARCH -j ${NCPU} build cmssw-tool-conf"
echo "${COMPILATION_CMD}"
eval $COMPILATION_CMD

#Find CMSSW IB to use to test externals
CMSSW_IB=$(scram -a $SCRAM_ARCH l -c $CMSSW_QUEUE | grep -v -f "${CMS_BOT_DIR}/ignore-releases-for-tests" | awk '{print $2}' | sort -r | head -1)
if [ ! -d ${CMSSW_IB} ] ; then
  echo "Setting up ${CMSSW_IB} area...."
  scram -a $SCRAM_ARCH project ${CMSSW_IB}
fi

#Setup newly build tools
cd ${CMSSW_IB}
CONF="config/toolbox/${SCRAM_ARCH}/tools/selected"
CONF_BACK="config/toolbox/${SCRAM_ARCH}/tools/selected.backup"
if [ ! -d ${CONF_BACK} ] ; then mv ${CONF} ${CONF_BACK} ; fi
rm -rf ${CONF}
TOOL_CONF=$(ls -td $WORKSPACE/$BUILD_DIR/$SCRAM_ARCH/cms/cmssw-tool-conf/*/tools/selected | head -1)
rsync -a ${TOOL_CONF}/ ${CONF}/
if [ -e "${CONF_BACK}/cmssw.xml" ] ; then cp ${CONF_BACK}/cmssw.xml ${CONF}/cmssw.xml ; fi
RMV_CMSSW_EXTERNAL="config/SCRAM/hooks/runtime/99-remove-release-external-lib"
if [ -f "${RMV_CMSSW_EXTERNAL}" ] ; then chmod +x ${RMV_CMSSW_EXTERNAL} ; fi
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
scram setup
scram setup self
eval `scram run -sh`
scram b echo_CXX >/dev/null 2>&1

#Find and checkout CMSSW packages which needs to be rebuild
CMSSW_DEP=$(scram build ${DEP_NAMES} | tr ' ' '\n' | grep '^cmssw/\|^self/' | cut -d"/" -f 2,3 | sort | uniq)
if [ "X${CMSSW_DEP}" != "X" ] ; then
  git cms-addpkg --ssh $CMSSW_DEP
fi

#Checkout any CMSSW PRs
for PR in $(echo $@ | tr ' ' '\n' | grep '/cmssw#' | sed 's|#|:|') ; do
  git cms-merge-topic --debug --ssh -u ${$PR}
done
echo "Please go to $CMSSW_BASE and checkout any extra CMSSW packages and rebuild."


