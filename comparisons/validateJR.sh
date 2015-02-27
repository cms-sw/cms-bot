baseA=$1
baseB=$2
diffN=$3
inList=$4

cWD=`pwd`
export pidList=""
nProc=$(getconf _NPROCESSORS_ONLN)
echo Start processing at `date`
grep root ${inList} | grep -v "#" | while read -r dsN fN procN comm; do 
    [ ! -f "${baseA}/${fN}" ] && echo Missing ${baseA}/${fN} && continue
    extN=all_${diffN}_${dsN}
    mkdir -p ${extN}
    cd ${cWD}/${extN}
    cp ~/tools/validate.C ./
    echo "Will run on ${fN} in ${cWD}/${extN}"
    echo "Now in `pwd`"
    g++ -shared -o validate.so validate.C `root-config --cflags ` -fPIC
    echo -e "gSystem->Load(\"libFWCoreFWLite.so\");\n AutoLibraryLoader::enable();\n 
    .x validate.C+(\"${extN}\", \"${baseA}/${fN}\", \"${baseB}/${fN}\", \"${procN}\");\n .qqqqqq" | root -l -b >& ${extN}.log &
# manually set the make flags, not needed in most cases
#    gSystem->SetMakeSharedLib(\"cd \$BuildDir ;g++  -c \$Opt -pipe -m64 -Wshadow -Wall -W -Woverloaded-virtual -fPIC -std=c++11 -Wno-deprecated-declarations -DG__MAXSTRUCT=36000 -DG__MAXTYPEDEF=36000 -DG__LONGLINE=4096 -pthread \$IncludePath \$SourceFiles ; g++ \$ObjectFiles -shared -Wl,-soname,\$LibName.so -m64 -Wl,--hash-style=gnu -O2  \$LinkedLibs -o \$SharedLib\");\n 
#    cout<< gSystem->GetMakeSharedLib()<<endl ;\n

    pidList=${pidList}" "${!}
    export pidList
    echo $pidList
    nRunning=`ps -p $pidList | grep -c root`
    while  [ "$nRunning" -ge "$nProc"  ]; do  
	nRunning=`ps -p $pidList | grep -c root`
        echo "limiting number of parallel processes"
	sleep 10
    done
    cd ${cWD}
    echo $pidList > lastlist.txt
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
