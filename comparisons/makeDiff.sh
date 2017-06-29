#!/bin/bash
f1=${1}
f2=${2}
fO=${3}
lMod=${4}
dOpt=${5}
dirPattern=${6}
dirPatternExclude=${7}
echo "Running on f1 ${f1} f2 ${f2} fO ${fO} lMod ${lMod} dOpt ${dOpt} dirPattern ${dirPattern} dirPatternExclude ${dirPatternExclude}"
echo -e "gROOT->SetStyle(\"Plain\");\n .L compareValHists.C+ \n\
 f1=new TFile(\"${f1}\");\n f2 = new TFile(\"${f2}\");\n compareAll(f1,f2,${lMod},${dOpt}, \"${dirPattern}\", \"${dirPatternExclude}\");\n\
.qqqqqq" | root -l -b
# this is normal for .qqqqqq. Do not pass it downstream.
exit_code=$?
if [ $exit_code -gt 0 ] ; then
  if [ $exit_code -eq 6 ] ; then
    exit 0
  fi
  exit $exit_code
fi

