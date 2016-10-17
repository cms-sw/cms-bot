baseA=$1
baseB=$2
diffN=$3
inList=$4
if [ "X$VALIDATE_C_SCRIPT" = "X" ] ; then
  VALIDATE_C_SCRIPT="${HOME}/tools/validate.C"
fi

cWD=`pwd`
export pidList=""
nProc=$(getconf _NPROCESSORS_ONLN)

function waitForProcesses {  
    pidList=${pidList}" "${!}
    export pidList
    echo $pidList
    nRunning=`ps -p $pidList | grep -c "^[ ]*[1-9]"`
    while [ "$nRunning" -ge "$nProc"  ]; do
        nRunning=`ps -p $pidList | grep -c "^[ ]*[1-9]"`
	echo "limiting number of parallel processes"
        sleep 10
    done
    cd ${cWD}
    echo $pidList > lastlist.txt
}


echo Start processing at `date`
touch missing_map.txt
ls -d ${baseA}/[1-9]* | sed 's|.*/||' | while read -r d; do
  grep  " $d/" ${inList} >& /dev/null || echo $d >> missing_map.txt
done
grep root ${inList} | grep -v "#" | while read -r dsN fN procN comm; do 
    [ ! -f "${baseA}/${fN}" ] && echo Missing ${baseA}/${fN}
    #process regular files first
    if [ -f "${baseA}/${fN}" ]; then
	extN=all_${diffN}_${dsN}
	mkdir -p ${extN}
	cd ${cWD}/${extN}
	cp ${VALIDATE_C_SCRIPT} ./
	echo "Will run on ${fN} in ${cWD}/${extN}"
	echo "Now in `pwd`"
	g++ -shared -o validate.so validate.C `root-config --cflags ` -fPIC
	echo -e "gSystem->Load(\"libFWCoreFWLite.so\");\n AutoLibraryLoader::enable();\n FWLiteEnabler::enable();\n 
    .x validate.C+(\"${extN}\", \"${baseA}/${fN}\", \"${baseB}/${fN}\", \"${procN}\");\n .qqqqqq" | root -l -b >& ${extN}.log &
	waitForProcesses
    fi
    #process miniAOD files now
    fNBase=`echo ${fN} | sed -e 's/.root$//g'`
    mFN="${fNBase}_inMINIAOD.root"
    if [ ! -f "${baseA}/${mFN}" ]; then
        mFN="${fNBase}_inMINIAODSIM.root"
    fi
    if [ -f "${baseA}/${mFN}" ]; then
	echo $mFN
	extmN=all_mini_${diffN}_${dsN}
	mkdir -p ${extmN}
	cd ${cWD}/${extmN}
	cp ${VALIDATE_C_SCRIPT} ./
	echo "Will run on ${mFN} in ${cWD}/${extmN}"
	echo "Now in `pwd`"
	echo -e "gSystem->Load(\"libFWCoreFWLite.so\");\n AutoLibraryLoader::enable();\n FWLiteEnabler::enable();\n
        .x validate.C+(\"${extmN}\", \"${baseA}/${mFN}\", \"${baseB}/${mFN}\", \"${procN}\");\n .qqqqqq" | root -l -b >& ${extmN}.log &
	waitForProcesses
    fi

done
allPids=`cat lastlist.txt`
nRunning=1
timeWaiting=0
while [ "$nRunning" -gt "0" -a "$timeWaiting" -lt "3600" ]; do
    nRunning=`ps -p $allPids | grep -c root`
    echo "waiting maximum 1 more Hour for the processes to finish"
    sleep 30
    timeWaiting=$((timeWaiting + 30))
done
echo done at `date`
