CMSREP_SERVER=cmsrep.cern.ch
CMSREP_IB_SERVER=cmsrep.cern.ch
export CMS_PYTHON_TO_USE="python"
if which python3 >/dev/null 2>&1 ; then export CMS_PYTHON_TO_USE="python3" ; fi

function cmsbuild_args()
{
  case $1 in
    CMSSW_*_SKYLAKEAVX512_X_* ) echo --vectorization haswell,skylake-avx512 ;;
    CMSSW_*_SANDYBRIDGE_X_* ) echo --vectorization sandybridge ;;
    CMSSW_*_HASWELL_X_* ) echo --vectorization haswell ;;
    * ) ;;
  esac
}
