#!/bin/bash -ex
#Add just for documentation purposes
echo "NO need to run it now. It has been run for CMSS_8_0_0"
exit 0

TAG=$1
[ "X$TAG" = "X" ] && exit 1
[ -d cmssw ] || git clone git@github.com:cms-sw/cmssw
rm -rf stitched
git clone git@github.com:cms-sw/stitched
pushd cmssw
  BRANCH=$(git branch | sed 's|.* CMSSW_|CMSSW_|' | grep CMSSW_ | head -1)
  git checkout $TAG
  COMMIT=$(git rev-list -n 1 $TAG)
popd
pushd stitched
  git symbolic-ref HEAD refs/heads/empty
  rm .git/index
  git clean -fdx 

  for pkg in DataFormats/Common DataFormats/FEDRawData DataFormats/FWLite DataFormats/Provenance DataFormats/StdDictionaries DataFormats/Streamer DataFormats/TestObjects DataFormats/WrappedStdDictionaries FWCore/Catalog FWCore/Common FWCore/Concurrency FWCore/FWLite FWCore/Framework FWCore/Integration FWCore/MessageLogger FWCore/MessageService FWCore/Modules FWCore/ParameterSet FWCore/PluginManager FWCore/PrescaleService FWCore/PythonParameterSet FWCore/ServiceRegistry FWCore/Services FWCore/Skeletons FWCore/Sources FWCore/TFWLiteSelector FWCore/TFWLiteSelectorTest FWCore/Utilities FWCore/Version IOMC/RandomEngine IOPool/Common IOPool/Input IOPool/Output IOPool/SecondaryInput IOPool/Streamer IOPool/TFileAdaptor SimDataFormats/RandomEngine Utilities/General Utilities/RFIOAdaptor Utilities/StorageFactory Utilities/Testing ; do
    sys=$(echo $pkg | sed 's|/.*||')
    mkdir -p $sys
    cp -r ../cmssw/$pkg $pkg
  done
  echo $COMMIT > .cmssw-commit
  git add .
  git commit -m "Initialize stitched based on $TAG"
  git checkout -b from-$TAG
  git checkout empty
popd
pushd cmssw
  git checkout $BRANCH
popd
