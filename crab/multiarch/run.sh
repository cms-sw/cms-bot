#!/bin/bash -e
JENKINS_ID=$(echo ${CRAB_ReqName} | sed 's|.*_||')
if [ "${JENKINS_ID}" = "" ] ; then JENKINS_ID="$$" ; fi
req=$(date +%s)
rm -rf crabout
mkdir -p crabout
pushd crabout
  for f in minbias.root FrameworkJobReport.xml run.txt ; do
    curl -s -L -o $f "https://muzaffar.web.cern.ch/crab-test/$f?req=${req}&uid=${JENKINS_ID}"
    [ -e $f ] || exit 1
  done
popd

rm -rf cmdrun
mkdir -p cmdrun
curl -s -L "https://muzaffar.web.cern.ch/cgi-bin/test-v2?start=-----------------------------------------&req=${req}&uid=${JENKINS_ID}"
pushd cmdrun
  req=$(date +%s)
  LRUN=${req}
  PRECMD=""
  RUN_GAP=0
  while [ $RUN_GAP -lt 7200 ] ; do
    req=$(date +%s)
    curl -s -L -o cmd.txt "https://muzaffar.web.cern.ch/crab-test/cmd.txt?req=${req}&uid=${JENKINS_ID}"
    cmd=$(grep "^cmd=${JENKINS_ID}=" cmd.txt || true)
    if [ "${cmd}" = "" ] ; then
      cmd=$(grep "^cmd=0=" cmd.txt || true)
    fi
    rm -f cmd.txt
    cmd=$(echo "$cmd" |  sed 's|^.*=|cmd=|')
    if [ "$cmd" = "cmd=0" ] ; then
      break
    fi
    if [ "${PRECMD}" = "$cmd" ] ; then
      xt=$(date +%s)
      xd=0
      while [ $xd -lt 9 ] ; do
        for i in 0 1 2 3 4 5 6 7 8 9 ; do
        for i in 0 1 2 3 4 5 6 7 8 9 ; do
        for i in 0 1 2 3 4 5 6 7 8 9 ; do
          true
        done
        done
        done
        let xd=$(date +%s)-${xt} || true
      done
      let RUN_GAP=$(date +%s)-${LRUN}
      b64=$(echo "previous_${cmd}" | base64)
      curl -s -L -X POST -d "$b64" "https://muzaffar.web.cern.ch/cgi-bin/test-v2?pending=++++++++++++++++++++++++++++++++++++++++++&${cmd}&req=${req}&uid=${JENKINS_ID}"
    else
      curl -s -L -o run.sh "https://muzaffar.web.cern.ch/crab-test/run.sh?req=${req}&uid=${JENKINS_ID}"
      chmod +x run.sh
      ./run.sh > run.log 2>&1 || true
      total_lines=$(cat run.log | wc -l)
      sline=1
      xline=5
      while [ $sline -le $total_lines ] ; do
        sed -n "${sline},+${xline}p" run.log | base64 > run.base64
        curl -s -L -X POST -d @run.base64 "https://muzaffar.web.cern.ch/cgi-bin/test-v2?result=${sline}of${total_lines}&${cmd}&req=${req}&uid=${JENKINS_ID}"
        sleep 1
        let sline=$sline+$xline+1
      done
      rm -f run.sh run.log run.base64
      PRECMD="${cmd}"
      LRUN=$(date +%s)
      RUN_GAP=0
    fi
  done
popd
req=$(date +%s)
curl -s -L "https://muzaffar.web.cern.ch/cgi-bin/test-v2?end=--------------------------------------------&req=${req}&uid=${JENKINS_ID}"
rm -rf cmdrun
mv crabout/* .
rm -rf crabout
cat run.txt
mv run.txt run.log
