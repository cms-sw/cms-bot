CMSREP_SERVER=cmsrep.cern.ch
CMSREP_IB_SERVER=cmsrep.cern.ch
CMSBUILD_OPTS_FILE="etc/build_options.sh"
BUILD_OPTS=""
MULTIARCH_OPTS=""
RELVAL_REAL_ARCH="AuthenticAMD"
umask 0002
export CMS_PYTHON_TO_USE="python"
if which python3 >/dev/null 2>&1 ; then export CMS_PYTHON_TO_USE="python3" ; fi

#called with $BUILD_OPTS $MULTIARCH_OPTS $ARCH
function cmsbuild_args()
{
  arg=""
  if [ "$1" != "" ] ; then
    BLD_OPTS=""
    for x in $(echo "$1" | tr ',' ' ') ; do
      case $x in
        upload_store ) ;;
        without:* )    arg="${arg} --build-without=$(echo $x    | sed 's|^without:||;s|:|,|g')" ;;
        system:* )     arg="${arg} --use-system-tools=$(echo $x | sed 's|^system:||;s|:|,|g')" ;;
        microarchs:* ) arg="${arg} --vectorization=$(echo $x    | sed 's|^microarchs:||;s|:|,|g')" ;;
        * ) BLD_OPTS="${BLD_OPTS},$x" ;;
      esac
    done
    [ "$BLD_OPTS" != "" ]  && arg="${arg} --build-options $(echo ${BLD_OPTS} | sed 's|^,||')"
  fi
  [ "$2" != "" ] && arg="${arg} --vectorization=$2"
  [ "${arg}" = "" ] || echo "${arg}"
}

function cmssw_default_target()
{
  case $1 in
    *SKYLAKE*|*SANDYBRIDGE*|*HASWELL*|*MULTIARCHS*) echo auto ;;
    *) echo default ;;
  esac
}
