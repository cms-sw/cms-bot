CMSREP_SERVER=cmsrep.cern.ch
CMSREP_IB_SERVER=cmsrep.cern.ch
function cmsbuild_args()
{
  case $1 in
    CMSSW_*_SKYLAKEAVX512_X_* ) echo --vectorization skylake-avx512 ;;
    CMSSW_*_MICROINS_X_* ) echo --vectorization sandybridge,haswell,skylake-avx512 ;;
    CMSSW_*_NEHALEM_X_* ) echo --vectorization nehalem ;;
    CMSSW_*_SANDYBRIDGE_X_* ) echo --vectorization sandybridge ;;
    CMSSW_*_HASWELL_X_* ) echo --vectorization haswell ;;
    * ) ;;
  esac
}
