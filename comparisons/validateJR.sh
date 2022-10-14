#!/bin/bash

function run_validate(){
  mkdir -p $1
  pushd $1
    echo "$(date): Will run on ${2} in ${1}"
    echo -e "gSystem->Load(\"libFWCoreFWLite.so\");\n
             AutoLibraryLoader::enable();\n
             FWLiteEnabler::enable();\n
             gSystem->Load(\"validate_C.so\");\n
             validate(\"${1}\", \"${baseA}/${2}\", \"${baseB}/${2}\", \"${3}\");\n
             .qqqqqq" | root -l -b >& ${1}.log
  popd
}

baseA=$1
baseB=$2
diffN=$3
inList=$4
if [ "X$VALIDATE_C_SCRIPT" = "X" ] ; then
  VALIDATE_C_SCRIPT="${HOME}/tools/validate.C"
fi

nProc=$(nproc)
touch missing_map.txt
dL=""
#check from map patterns to the local
while read -r dsN fNP procN comm; do 
    dP=`echo "${fNP}" | sed -e 's?/[^/]*.root??g'`; d=`echo ${baseA}/$dP | cut -d" " -f1 `  
    [ -d "${d}" ] && dL="$dL ${d}/"
done< <(grep root ${inList} |  grep -v "#")
#check the found mapped list with all that we have
ls -d ${baseA}/[1-9]* | while read -r d; do 
  echo "${dL}" | grep  " $d/" >& /dev/null || echo $d >> missing_map.txt
done

mkdir -p validate_lib
pushd validate_lib
    cp ${VALIDATE_C_SCRIPT} ./validate.C
    echo -e "gSystem->Load(\"libFWCoreFWLite.so\");\n AutoLibraryLoader::enable();\n FWLiteEnabler::enable();\n .L validate.C+\n .qqqqqq" | root -l -b
popd
export LD_LIBRARY_PATH=`pwd`/validate_lib:${LD_LIBRARY_PATH}
grep root ${inList} | grep -v "#" | while read -r dsN fNP procN comm; do
    #fNP can be a pattern: path-expand it first
    fN=`echo ${baseA}/${fNP} | cut -d" " -f1 | sed -e "s?^${baseA}/??g"`
    #[ ! -f "${baseA}/${fN}" ] && echo Missing ${baseA}/${fN}
    #process regular files first; need files both in baseA and baseB
    if [ -f "${baseA}/${fN}" -a -f "${baseB}/${fN}" ]; then
        extN=all_${diffN}_${dsN}
        run_validate "all_${diffN}_${dsN}" "${fN}" "${procN}" &
        while [ $(jobs -p | wc -l) -ge ${nProc} ] ; do sleep 5 ; done
    fi
    #process miniAOD files now
    fNBase=`echo ${fN} | sed -e 's/.root$//g'`
    mFN="${fNBase}_inMINIAOD.root"
    if [ ! -f "${baseA}/${mFN}" ]; then
        mFN="${fNBase}_inMINIAODSIM.root"
    fi
    #need files both in baseA and baseB
    if [ -f "${baseA}/${mFN}" -a -f "${baseB}/${mFN}" ]; then
        echo $mFN
        run_validate "all_mini_${diffN}_${dsN}" "${mFN}"  "${procN}" &
        while [ $(jobs -p | wc -l) -ge ${nProc} ] ; do sleep 5 ; done
    fi
done
wait
rm -rf validate_lib
