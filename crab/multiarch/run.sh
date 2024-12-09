#!/bin/bash -e
req=$(date +%s)
rm -rf crabout
mkdir -p crabout
pushd crabout
  for f in minbias.root FrameworkJobReport.xml cmsRun.out ; do
    curl -s -L -o $f "https://muzaffar.web.cern.ch/crab-test/$f?req=${req}"
    [ -e $f ] || exit 1
  done
popd

rm -rf cmdrun
mkdir -p cmdrun
curl -s -L "https://muzaffar.web.cern.ch/cgi-bin/test-v2?req=${req}&start=1"
pushd cmdrun
  LRUN=$(date +%s)
  PRECMD=""
  RUN_GAP=0
  while [ $RUN_GAP -lt 7200 ] ; do
    cmd=$(curl -s -L "https://muzaffar.web.cern.ch/crab-test/cmd?req=${req}" | grep "cmd=" || echo "cmd=")
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
      b64=$(echo -n "previous_${cmd}" | base64)
      curl -s -L -X POST -d "$b64" "https://muzaffar.web.cern.ch/cgi-bin/test-v2?$cmd&req=${req}"
    else
      curl -s -L -o run.sh "https://muzaffar.web.cern.ch/crab-test/run.sh?req=${req}"
      chmod +x run.sh
      ./run.sh > run.log 2>&1 || true
      total_lines=$(cat run.log | wc -l)
      sline=1
      xline=20
      while [ $sline -le $total_lines ] ; do
        sed -n "${sline},+${xline}p" run.log | base64 > run.base64
        let sline=$sline+$xline+1
        curl -s -L -X POST -d @run.base64 "https://muzaffar.web.cern.ch/cgi-bin/test-v2?$cmd&req=${req}"
      done
      rm -f run.sh run.log run.base64
      PRECMD="${cmd}"
      LRUN=$(date +%s)
      RUN_GAP=0
    fi
  done
popd
curl -s -L "https://muzaffar.web.cern.ch/cgi-bin/test-v2?req=${req}&end=1"
rm -rf cmdrun
mv crabout/* .
rm -rf crabout
mv cmsRun.out run.log
cat run.log
