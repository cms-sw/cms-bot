#!/bin/bash
#run this command for once to create the data file
#for releases
#find /afs/cern.ch/cms/slc[5-7]* -maxdepth 3 -type d -print -exec fs lq {} \; | grep -v 'Volume Name' | sed 'N;s/\n/ /' | uniq -c -f2 > slc567
#for ibs
#find /afs/cern.ch/cms/sw/ReleaseCandidates/ -maxdepth 3 -type d -print -exec fs lq {} \; |grep -v '^Volume' | sed 'N;s/\n/ /' | uniq -c -f3 >ibs

sum=0
count=0
while read line ; do
  echo $line | awk '{print $4}'
  let sum=$sum+`echo $line | awk '{print $4}'`
   let count=$count+1
done < slc567
echo "number of dirs: $count"  
echo "total size : $sum"
size=`expr $sum / 1000000`
echo "total size GB $size"
