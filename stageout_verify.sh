#!/bin/sh
#
trap 'exit 1' 1 2 3 15
trap '/bin/rm -f /tmp/stageout_verify_$$.bin 1> /dev/null 2>&1' 0
#
#
#
# destinations the test can use:

voms-proxy-init -voms cms
voms-proxy-info -all

STAGEOUT="gsiftp://gridftp.echo.stfc.ac.uk/cms: \
          gsiftp://eoscmsftp.cern.ch/eos/cms \
          srm://srmcms.pic.es:8443/srm/managerv2?SFN=/pnfs/pic.es/data/cms/disk \
          srm://cmssrm-kit.gridka.de:8443/srm/managerv2?SFN=/pnfs/gridka.de/cms/disk-only \
          davs://cmswebdav-kit.gridka.de:2880/pnfs/gridka.de/cms/disk-only \
          davs://srmcms.pic.es:8459/pnfs/pic.es/data/cms/disk \
          davs://ceph-svc02.gridpp.rl.ac.uk:1094/ \
          davs://ceph-gw7.gridpp.rl.ac.uk:1094/ \
          davs://eoscms.cern.ch:443/eos/cms \
          davs://webdav.echo.stfc.ac.uk:1094/ \
          root://eoscms.cern.ch//eos/cms \
          root://xrootd.echo.stfc.ac.uk/ \
          root://xrootd-cmst1-door.pic.es:1094//pnfs/pic.es/data/cms/disk"
PREFIX="/store/test/cmsbuild"
#
# create a small 64kB test file:
/usr/bin/head -c 65536 </dev/urandom 1>/tmp/stageout_verify_$$.bin
#
# calculate Adler-32 checksum:
CHKSUM=`/usr/bin/xrdadler32 /tmp/stageout_verify_$$.bin | /usr/bin/awk '{print $1; exit}'`
echo "Adler-32 checksum of test file stageout_verify_$$.bin is ${CHKSUM}"
#
# loop over stage-out protocols and verify at a test site:
# overall fails protocols:
MRC=""
SUMMARY=""
echo ""
for PROTO in root gsiftp srm davs; do
   PASSED=0
   TOTAL=0
   echo "Stage-out protocol ${PROTO} .... "
   #
   for DEST in ${STAGEOUT}; do
      if [[ "${DEST}" =~ ^${PROTO}:// ]]; then
         let TOTAL=$TOTAL+1
         echo "  using ${DEST}"
         /usr/bin/gfal-copy -t 90 --checksum ADLER32:${CHKSUM} \
                            file:///tmp/stageout_verify_$$.bin \
                            ${DEST}${PREFIX}/stageout_verify_$$.bin 1>/dev/null
         RC=$?
         echo "  gfal-copy, rc=${RC}"
         if [ ${RC} -eq 0 ]; then
            let PASSED=$PASSED+1
            /usr/bin/gfal-rm -t 90 ${DEST}${PREFIX}/stageout_verify_$$.bin 1>/dev/null
            echo "  gfal-rm, rc=$?"
         fi
      fi
   done
   SUMMARY="${SUMMARY} ${PROTO}($PASSED/$TOTAL)"
   if [ $PASSED -eq 0 ] ; then
       echo "Failed: $PASSED/$TOTAL"
       MRC="${MRC} ${PROTO}($PASSED/$TOTAL)"
   else
       echo "Passed: $PASSED/$TOTAL"
   fi
   echo ""
done
#
echo "Test Summary:${SUMMARY}"
if [ "${MRC}" != "" ]; then
   echo "Failed protocol(s): ${MRC}"
   exit 1
fi
exit 0
