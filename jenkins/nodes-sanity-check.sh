paths=("/afs" "/cvmfs" "/cvmfs/cms.cern.ch" "/cvmfs/cms-ci.cern.ch" "/cvmfs/cms-ib.cern.ch" "/cvmfs/grid.cern.ch" "/cvmfs/unpacked.cern.ch")

# Checking that paths are acessible
for path in ${paths[@]}; do
    echo "Checking ${path} for host $(hostname)"
    ls ${path} >/dev/null 2>&1 && echo -e "... OK!" || exit 1
done

arch=$(uname -r | grep -o "el[0-9]")

if [[ $arch == "el7"  ]]; then
    arch="cc7"
fi

# Checking that singularity can start
echo "Checking that singularity can start a container on $(hostname)"
/cvmfs/cms.cern.ch/common/cmssw-${arch} --command-to-run ls >/dev/null 2>&1 && echo -e "... OK!" || exit 1
