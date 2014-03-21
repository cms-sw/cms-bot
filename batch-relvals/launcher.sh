#!/bin/bash

#$1 is the file with the workflows
#$2 is your home directory on afs
#$3 is the release for which you want to run the relvals
# Example: ./launcher.sh wfs/1wfs $HOME CMSSW_7_1_X_2014-03-21-0200

while read WFS; do
  mkdir -p outs
  NUMBER=$(echo $WFS | sed -e 's/_.*//g' )
  echo $NUMBER
  HOME=$(echo $2 | sed -e 's/\//\\\//g' )
  echo $HOME
  mkdir -p outs/$WFS

  #create script
  cp base-cmssw_wf.sh cmssw_wf$NUMBER.sh
  sed -i "s/NUM_WF/$NUMBER/g" cmssw_wf$NUMBER.sh
  sed -i "s/DIRECTORY/$WFS/g" cmssw_wf$NUMBER.sh
  sed -i "s/HOME_DIR/$HOME/g" cmssw_wf$NUMBER.sh
  sed -i "s/RELEASE/$3/g" cmssw_wf$NUMBER.sh

  #submit job
  bsub -q 1nh -R type="SLC6_64" -o outs/$WFS cmssw_wf$NUMBER.sh
done < $1
