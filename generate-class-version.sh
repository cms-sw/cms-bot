#!/bin/bash

function get_package_dir(){
  local base_dir=""
  for dir in ${PROJ_DIRS} ; do
    if [ -e ${dir}/src/$1 ] ; then
      base_dir=${dir}/src/$1
      break
    fi
  done
  xml_files=""
  for xml in $2 ; do
    xml_files="${base_dir}/src/${xml} ${xml_files}"
  done
  echo ${xml_files}
}

function file_to_url(){
  tag=$(echo $1 | tr / '\n' | grep -E '^CMSSW_[0-9]+_[0-9]+_' | tail -1)
  src_file=$(echo $1 | sed "s|.*/${tag}/src/||")
  echo "<a href=\"https://github.com/cms-sw/cmssw/blob/${tag}/${src_file}\">${src_file}</a>"
}

function run_edmDumpClassVersion(){
  local url=$(file_to_url ${2})
  echo "Working on <a href=\"class_versions/${3}\">$3/$1</a>" > class_versions/${3}/${1}_${4}.msg
  if ! edmDumpClassVersion -l lib${1}.so -x $2 -o class_versions/${3}/${1}_${4}.json > class_versions/${3}/${1}_${4}.log 2>&1 ; then
    sed -i -e "s|${2}|${url}|" class_versions/${3}/${1}_${4}.log
    echo "  FAILED: <a href=\"class_versions/${3}/edmDumpClassVersion.html\">$3/$1</a>" >> class_versions/${3}/${1}_${4}.msg
  fi
}

PROD_TYPE="ALL_PRODS"
PROJ_DIRS="$CMSSW_BASE"
if [ "$1" = "--baseline" ] ; then
  PROD_TYPE="ALL_EXTERNAL_PRODS"
  PROJ_DIRS="$CMSSW_RELEASE_BASE $CMSSW_FULL_RELEASE_BASE"
fi

cd $CMSSW_BASE
[ -e prods.txt ]    || scram b echo_${PROD_TYPE} | grep '_PRODS =' | sed 's|.*= ||' | tr ' ' '\n' | sort | uniq | grep '[a-zA-Z]' > prods.txt
[ -e lcgdict.txt ]  || cat prods.txt | sed 's|^|echo_|;s|$|_LCGDICTS|' | xargs scram b | grep -v ' = *$' > lcgdict.txt
[ -e packages.txt ] ||sed 's|_LCGDICTS = .*||;s|^|echo_|' lcgdict.txt | xargs scram b | grep ' cmssw/' | sed 's|  *||g;s|cmssw/||' | cut -d/ -f1,2 > packages.txt
if [ ! -e override-xml.txt ] ; then
touch override-xml.txt
for dir in ${PROJ_DIRS} ; do
  [ -d $dir/.SCRAM/${SCRAM_ARCH}/BuildFiles/src ] || continue
  grep -A1 -R LCG_DICT_XML $dir/.SCRAM/${SCRAM_ARCH}/BuildFiles/src | grep -v 'LCG_DICT_XML' | grep /BuildFile.xml | sed 's|.*/BuildFiles/src/||;s|/BuildFile.xml- *"|=|;s|"$||' > xmls.txt
  for p in $(sed 's|=.*||' xmls.txt) ; do
    grep -q "^${p}=" override-xml.txt && continue
    grep "^${p}=" xmls.txt >> override-xml.txt
  done
  rm -f xmls.txt
done
fi

NUM_PROC=$(nproc)
rm -rf class_versions
for pkg in $(cat packages.txt | sed 's|.*=||' | sort | uniq) ; do
  mkdir -p class_versions/${pkg}
  for p in $(grep "=${pkg}$" packages.txt | sed 's|=.*$||') ; do
    xml="classes_def.xml"
    [ $(grep "^${pkg}=" override-xml.txt |wc -l) -gt 0 ] && xml=$(grep "^${pkg}=" override-xml.txt | sed 's|.*=||')
    case $p in
      *CudaAsync)  xml="alpaka/classes_cuda_def.xml" ;;
      *ROCmAsync)  xml="alpaka/classes_rocm_def.xml" ;;
      *SerialSync) xml="alpaka/classes_serial_def.xml" ;;
      *TbbAsync)   xml="alpaka/classes_tbb_def.xml" ;;
    esac
    cnt=0
    for xml in $(get_package_dir $pkg "${xml}") ; do
      while [ $(jobs -p | wc -l) -ge ${NUM_PROC} ] ; do sleep 0.1 ; done
      let cnt=$cnt+1
      echo "Running edmDumpClassVersion $p $xml"
      run_edmDumpClassVersion "$p" "$xml" "$pkg" "$cnt" &
    done
  done
done
wait

echo "Done runnin edmDumpClassVersion"
echo "Processing logs ..."

echo "<html><head></head><body><pre>" > class_versions.html
for pkg in $(cat packages.txt | sed 's|.*=||' | sort | uniq) ; do
  [ -d class_versions/${pkg} ] || continue
  for log in $(find class_versions/${pkg} -name '*.log' -type f); do
    if [ -s $log ] ; then
      echo "<html><head></head><body><pre>" > class_versions/${pkg}/edmDumpClassVersion.html
      cat $log  >> class_versions/${pkg}/edmDumpClassVersion.html
      echo "</pre></body></html>" >> class_versions/${pkg}/edmDumpClassVersion.html
    fi
    rm -f $log
  done
  for log in $(find class_versions/${pkg} -name '*.msg' -type f); do
    cat $log >> class_versions.html
    rm -f $log
  done
done
echo "</pre></body></html>" >> class_versions.html
