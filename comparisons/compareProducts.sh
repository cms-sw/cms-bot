#!/bin/bash

fA=`echo $1`
if [ ! -f "${fA}" ]; then
    echo ${fA} does not exist
    exit 17
fi
fB=`echo $2`
if [ ! -f "${fB}" ]; then
    echo ${fB} does not exist
    exit 17
fi

procF=$3
if [ "x${procF}" == "x" ]; then
    procF="_RECO"
fi

absMin=$4
if [ "x${absMin}" == "x" ]; then
    absMin=100
fi
dptMin=$5
if [ "x${dptMin}" == "x" ]; then
    dptMin=20
fi

useUnpacked=$6
if [ "x${useUnpacked}" == "x" ]; then
    useUnpacked=no
fi

echo "Checking process ${procF} ${fA} and ${fB} with useUnpacked=${useUnpacked} (if above ${absMin} or ${dptMin}%):"

case `basename $fA` in
  step*.root)
    ds=`date -u +%s.%N`
    os=os.${ds}
    edmEventSize -v ${fA} > ${os} &

    ns=ns.${ds}
    edmEventSize -v ${fB} > ${ns} &
    wait
    grep ${procF} ${os} ${ns} | sed -e "s/${os}:/os /g;s/${ns}:/ns /g" | absMin=${absMin} dptMin=${dptMin} useUnpacked=${useUnpacked} awk -f compareProducts.awk

    rm ${os} ${ns}
  ;;
  step*sizes*.txt)
    grep ${procF} ${fA} ${fB} | sed -e "s/${fA}:/os /g;s/${fB}:/ns /g" | absMin=${absMin} dptMin=${dptMin} useUnpacked=${useUnpacked} awk -f compareProducts.awk
  ;;
  *)
    echo "First two inputs $fA and $fB should be step*.root or step*_sizes.txt"
    exit 18
  ;;
esac
