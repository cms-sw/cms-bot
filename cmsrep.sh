CMSREP_SERVER=cmsrep.cern.ch
CMSREP_IB_SERVER=cmsrep.cern.ch
function cmsbuild_args()
{
  case $1 in
    CMSSW_*_SKYLAKEAVX512_X_* ) echo --vectorization skylake-avx512 ;;
    CMSSW_*_MICROINS_X_* ) echo --vectorization sandybridge,haswell,broadwell,skylake,skylake-avx512 ;;
    CMSSW_*_NEHALEM_X_* ) echo --vectorization nehalem ;;
    CMSSW_*_SANDYBRIDGE_X_* ) echo --vectorization sandybridge ;;
    CMSSW_*_HASWELL_X_* ) echo --vectorization haswell ;;
    CMSSW_*_BROADWELL_X_* ) echo --vectorization broadwell ;;
    CMSSW_*_SKYLAKE_X_* ) echo --vectorization skylake ;;
    * ) ;;
  esac
}
