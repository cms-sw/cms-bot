#!/bin/bash -e
source $(dirname $0)/setup-pr-test-env.sh
toolconf_file=$CMSSW_BASE/config/toolbox/$SCRAM_ARCH/tools/selected/python-paths.xml
[ -f $toolconf_file ] || exit 0
tool_conf=$(grep -E '/cms/cmssw-(patch-|)tool-conf/' $toolconf_file | tr ' ' '\n' | grep -E '/cmssw-(patch-|)tool-conf/' | sed 's|.*=||;s|"||g' | rev  | cut -d/ -f4- | rev)
tool_pkg=$(echo $tool_conf | rev | cut -d/ -f1-3 | rev | tr '/' '+')
base_dir=$(echo $tool_conf | sed "s|/$SCRAM_ARCH/.*||")
cmspkg="${base_dir}/common/cmspkg -a $SCRAM_ARCH"
deps=$(${cmspkg} env -- rpm -q --requires ${tool_pkg} | tr '\n' ' ')
if [ $(ls -d ${base_dir}/$SCRAM_ARCH/*.log 2>/dev/null |wc -l) -gt 0 ] ; then
  cat ${base_dir}/$SCRAM_ARCH/*.log | grep "${base_dir}/${SCRAM_ARCH}/" | grep -i ': No such file or directory' > ${WORKSPACE}/externals-checks-missing.log || true
fi
echo "Looking in to ${tool_conf} ${tool_pkg} with base dir ${base_dir}"
mkdir -p ${WORKSPACE}/external_checks
cnt=0
for init in $(find ${base_dir}/${SCRAM_ARCH} -path '*/etc/profile.d/init.sh') ; do
  pkg_dir=$(echo $init | sed 's|/etc/profile.d/init.sh||')
  pkg=$(echo $pkg_dir | sed "s|$base_dir/$SCRAM_ARCH/||;s|/|+|g")
  pkg_name=$(echo ${pkg} | cut -d+ -f2)
  echo "Checking: $pkg $pkg_dir"
  if [ $(echo " ${deps} " | grep " ${pkg} "| wc -l) -eq 0 ] ; then
    echo "  Skipping: $pkg is not deps of ${tool_pkg}"
    continue
  fi
  build_dir=$(${cmspkg} env -- rpm -q --scripts $pkg | grep '/tmp/BUILDROOT/' | head -1 | sed 's|/tmp/BUILDROOT/.*||;s|^[^/]*/|/|')
  touch ${WORKSPACE}/external_checks/${pkg_name}.txt
  [ "${build_dir}" != "" ] || continue
  (grep "${build_dir}/" -Ir ${pkg_dir} 2>&1 | grep -v '/direct_url.json:' >${WORKSPACE}/external_checks/${pkg_name}.txt) || true
  if [ -f ${WORKSPACE}/externals-checks-missing.log ] ; then
    grep "${pkg_dir}" ${WORKSPACE}/externals-checks-missing.log >> ${WORKSPACE}/external_checks/${pkg_name}.txt || true
  fi
  if [ -s ${WORKSPACE}/external_checks/${pkg_name}.txt ] ; then
    cat ${WORKSPACE}/external_checks/${pkg_name}.txt
    let cnt=$cnt+1
  else
    rm -f ${WORKSPACE}/external_checks/${pkg_name}.txt
    echo "  OK: No relocatable path found"
  fi
done
[ $cnt -eq 0 ] && echo "<html><body>All OK</body></html>" >  ${WORKSPACE}/external_checks/index.html
if [ "${DRY_RUN}" = "" ] ; then
  echo 'CMSSWTOOLCONF_CHECKS;OK,Externals path checks,See Log,external_checks' >> ${RESULTS_DIR}/externals_checks.txt
  prepare_upload_results
fi
