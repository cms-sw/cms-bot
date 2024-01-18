CMSREP_SERVER=cmsrep.cern.ch
CMSREP_IB_SERVER=cmsrep.cern.ch
export CMS_PYTHON_TO_USE="python"
if which python3 >/dev/null 2>&1 ; then export CMS_PYTHON_TO_USE="python3" ; fi

function cmsbuild_args()
{
  case $1 in
    CMSSW_*_SKYLAKEAVX512* ) echo --vectorization haswell,skylake-avx512 ;;
    CMSSW_*_SANDYBRIDGE* ) echo --vectorization sandybridge ;;
    CMSSW_*_HASWELL* ) echo --vectorization haswell ;;
    CMSSW_*_MULTIARCHS* ) echo --vectorization x86-64-v3 ;;
    * ) ;;
  esac
}
