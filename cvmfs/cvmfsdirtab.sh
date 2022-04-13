#!/bin/bash
#Shared files
for cmsdir in "$@" ; do
  if [ $(ls ${CVMFS_DIR}/$cmsdir -d 2>/dev/null | wc -l) -eq 0 ] ; then exit 0 ; fi
  echo "/${cmsdir}/share"
  for x in cms/data-L1Trigger-L1TMuon cms/data-GeneratorInterface-EvtGenInterface 'cms/data-MagneticField-Interpolation/*' ; do
    echo "/${cmsdir}/share/${x}"
  done

  #cmssw externals
  echo "/${cmsdir}/*_*_*/external/*"
  for x in blackhat boost cuda geant4 geant4-G4EMLOW herwigpp madgraph5amcatnlo py2-pippkgs py2-pippkgs_depscipy sherpa rivet; do
    echo "/${cmsdir}/*_*_*/external/${x}/*"
  done

  #Some special directories
  for x in cms lcg lcg/root ; do
    echo "/${cmsdir}/*_*_*/${x}"
  done

  #for cmssw releases
  for x in cmssw cmssw-patch ; do
    echo "/${cmsdir}/*_*_*/cms/${x}/CMSSW_*/src"
    echo "/${cmsdir}/*_*_*/cms/${x}/CMSSW_*"
  done
done
