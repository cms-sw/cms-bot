#!/bin/bash

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

grep root ${inList} | grep -v "#" | while read -r dsN fNP procN comm; do
    #fNP can be a pattern: path-expand it first
    fN=`echo ${baseA}/${fNP} | cut -d" " -f1 | sed -e "s?^${baseA}/??g"`
    #[ ! -f "${baseA}/${fN}" ] && echo Missing ${baseA}/${fN}
    #process regular files first; need files both in baseA and baseB
    if [ -f "${baseA}/${fN}" -a -f "${baseB}/${fN}" ]; then
	extN=all_${diffN}_${dsN}
	mkdir -p ${extN}
	pushd ${extN}
	  cp ${VALIDATE_C_SCRIPT} ./
	  echo "Will run on ${fN} in ${extN}"
	  g++ -shared -o validate.so validate.C `root-config --cflags ` -fPIC
	  echo -e "gSystem->Load(\"libFWCoreFWLite.so\");\n AutoLibraryLoader::enable();\n FWLiteEnabler::enable();\n
                  .x validate.C+(\"${extN}\", \"${baseA}/${fN}\", \"${baseB}/${fN}\", \"${procN}\");\n .qqqqqq" | root -l -b >& ${extN}.log &
        popd
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
	extmN=all_mini_${diffN}_${dsN}
	mkdir -p ${extmN}
	pushd ${extmN}
	  cp ${VALIDATE_C_SCRIPT} ./
	  echo "$(date): Will run on ${mFN} in ${extmN}"
	  echo -e "gSystem->Load(\"libFWCoreFWLite.so\");\n AutoLibraryLoader::enable();\n FWLiteEnabler::enable();\n
                  .x validate.C+(\"${extmN}\", \"${baseA}/${mFN}\", \"${baseB}/${mFN}\", \"${procN}\");\n .qqqqqq" | root -l -b >& ${extmN}.log &
        popd
        while [ $(jobs -p | wc -l) -ge ${nProc} ] ; do sleep 5 ; done
    fi
done
wait
