CMSREP_SERVER=cmsrep.cern.ch
CMSREP_IB_SERVER=cmsrep.cern.ch
export CMS_PYTHON_TO_USE="python"
if which python3 >/dev/null 2>&1 ; then export CMS_PYTHON_TO_USE="python3" ; fi

function cmsbuild_args()
{
  case $1 in
    CMSSW_*SKYLAKEAVX512* ) echo --vectorization haswell,skylake-avx512 ;;
    CMSSW_*_SANDYBRIDGE* ) echo --vectorization sandybridge ;;
    CMSSW_*_HASWELL* ) echo --vectorization haswell ;;
    * ) ;;
  esac
}
