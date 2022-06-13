#!/bin/bash
#Shared files
for cmsdir in "$@" ; do
  tmpfile=$(mktemp)
  if [ $(ls ${CVMFS_DIR}/$cmsdir -d 2>/dev/null | wc -l) -eq 0 ] ; then exit 0 ; fi
  echo "/${cmsdir}/share" > $tmpfile
  for x in cms/data-L1Trigger-L1TMuon cms/data-GeneratorInterface-EvtGenInterface 'cms/data-MagneticField-Interpolation/*' ; do
    echo "/${cmsdir}/share/${x}" >> $tmpfile
  done

  #cmssw externals
  echo "/${cmsdir}/*_*_*/external/*" >> $tmpfile
  for x in blackhat boost cuda geant4 geant4-G4EMLOW herwigpp madgraph5amcatnlo py2-pippkgs py2-pippkgs_depscipy sherpa rivet; do
    echo "/${cmsdir}/*_*_*/external/${x}/*" >> $tmpfile
  done

  #Some special directories
  for x in cms lcg lcg/root ; do
    echo "/${cmsdir}/*_*_*/${x}" >> $tmpfile
  done

  #for cmssw releases
  for x in cmssw cmssw-patch ; do
    echo "/${cmsdir}/*_*_*/cms/${x}/CMSSW_*/src" >> $tmpfile
    echo "/${cmsdir}/*_*_*/cms/${x}/CMSSW_*" >> $tmpfile
  done
  if [[ "$cmsdir" == "spack" ]]; then
    # First sed: remove "cms/", "lcg/", "external/" since spack install tree is flat
    # Second sed: replace CMS' top-level directory name (<os>_<arch>_<comp><compvers>) with spack's (<platform>-<os>-<arch>/<comp>-<compvers>)
    # Third sed: use spack package names for madgraph5amcatnlo and geant4-G4EMLOW
    # Fourth sed: replace CMS' package directory name (<pkgname>/<version>-<hash>) with spack's (<pkgname>-<version>-<hash>)
    cat $tmpfile | sed -e 's#/lcg/#/#g;s#/external/#/#g;s#/cms/#/#g' | sed -e "s#/${cmsdir}/._._./#/${cmsdir}/*-*-*/*-*/#" | sed -e 's#madgraph5amcatnlo#madgraph5amc#g;s#geant4-##g'  | sed -e 's#/[*]$#-*#g'
  else
    cat $tmpfile
  fi
  rm $tmpfile
done
