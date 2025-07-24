SINGULARITY=$1
shift
PATHS=$@

# Checking that paths are acessible
for path in ${PATHS[@]}; do
    echo "Checking ${path} for host $(hostname)"
    timeout -k 1m 30s ls ${path} >/dev/null 2>&1 && echo -e "... OK!" || echo "ERROR accessing ${path}"
done

arch=$(uname -r | grep -o "el[0-9]")

if [[ $arch == "el7"  ]]; then
    arch="cc7"
fi

if [ "$SINGULARITY" == "true" ]; then
    # Checking that singularity can start
    echo "Checking that singularity can start a container on $(hostname)"
    /cvmfs/cms.cern.ch/common/cmssw-${arch} --command-to-run ls >/dev/null 2>&1 && echo -e "... OK!" || echo "ERROR starting singularity"
fi
