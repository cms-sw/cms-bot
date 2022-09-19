#!/bin/bash -e
source $(dirname $0)/setup-pr-test-env.sh
toolconf_file=$CMSSW_BASE/config/toolbox/$SCRAM_ARCH/tools/selected/python-paths.xml
[ -f $toolconf_file ] || exit 0
tool_conf=$(grep /cms/cmssw-tool-conf/ $toolconf_file | tr ' ' '\n' | grep /cmssw-tool-conf/ | sed 's|.*=||;s|"||g' | rev  | cut -d/ -f4- | rev)
tool_pkg=$(echo $tool_conf | rev | cut -d/ -f1-3 | rev | tr '/' '+')
base_dir=$(echo $tool_conf | sed "s|/$SCRAM_ARCH/.*||")
cmspkg="${base_dir}/common/cmspkg -a $SCRAM_ARCH"
deps=$(${cmspkg} env -- rpm -q --requires ${tool_pkg} | tr '\n' ' ')
LOGFILE=$WORKSPACE/externals-checks.log
rm -f $LOGFILE ; touch $LOGFILE
for init in $(find ${base_dir}/${SCRAM_ARCH} -path '*/etc/profile.d/init.sh') ; do
  pkg_dir=$(echo $init | sed 's|/etc/profile.d/init.sh||')
  pkg=$(echo $pkg_dir | sed "s|$base_dir/$SCRAM_ARCH/||;s|/|+|g")
  echo "Checking: $pkg $pkg_dir"
  [ $(echo " ${deps} " | grep " ${pkg} "| wc -l) -gt 0 ] || continue
  build_dir=$(${cmspkg} env -- rpm -q --scripts $pkg | grep '/tmp/BUILDROOT/' | head -1 | sed 's|/tmp/BUILDROOT/.*||;s|^[^/]*/|/|')
  [ "${build_dir}" != "" ] || continue
  echo "Search $build_dir under ${pkg_dir}" >> $LOGFILE
  for m in $(grep "${build_dir}/" -Ir ${pkg_dir} | grep -v '/direct_url.json:'); do
    echo "Found:$m" >> $LOGFILE
  done
done
echo 'CMSSWTOOLCONF_CHECKS;OK,Externals path checks,See Log,externals-checks.log' >> ${RESULTS_DIR}/externals.txt
prepare_upload_results
