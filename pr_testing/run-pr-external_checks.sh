#!/bin/bash -e
source $(dirname $0)/setup-pr-test-env.sh
toolconf_file=$CMSSW_BASE/config/toolbox/$SCRAM_ARCH/tools/selected/python-paths.xml
[ -f $toolconf_file ] || exit 0
tool_conf=$(grep -E '/cms/cmssw-(patch-|)tool-conf/' $toolconf_file | tr ' ' '\n' | grep -E '/cmssw-(patch-|)tool-conf/' | sed 's|.*=||;s|"||g' | rev  | cut -d/ -f4- | rev)
tool_pkg=$(echo $tool_conf | rev | cut -d/ -f1-3 | rev | tr '/' '+')
base_dir=$(echo $tool_conf | sed "s|/$SCRAM_ARCH/.*||")
cmspkg="${base_dir}/common/cmspkg -a $SCRAM_ARCH"
deps=$(${cmspkg} env -- rpm -q --requires ${tool_pkg} | tr '\n' ' ')
if [ -f ${base_dir}/$SCRAM_ARCH/${tool_pkg}.log ] ; then
  grep "${base_dir}/${SCRAM_ARCH}/" ${base_dir}/$SCRAM_ARCH/${tool_pkg}.log | grep -i ': No such file or directory' > ${WORKSPACE}/externals-checks-missing.log || true
fi
echo "Looking in to ${tool_conf} ${tool_pkg} with base dir ${base_dir}"
mkdir -p ${WORKSPACE}/external_checks
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
  grep "${build_dir}/" -Ir ${pkg_dir} >${WORKSPACE}/external_checks/${pkg_name}.txt 2>&1 || true
  if [ -f ${WORKSPACE}/externals-checks-missing.log ] ; then
    grep "${pkg_dir}" ${WORKSPACE}/externals-checks-missing.log >> ${WORKSPACE}/external_checks/${pkg_name}.txt || true
  fi
  cat ${WORKSPACE}/external_checks/${pkg_name}.txt
done
if [ "${DRY_RUN}" = "" ] ; then
  echo 'CMSSWTOOLCONF_CHECKS;OK,Externals path checks,See Log,external_checks' >> ${RESULTS_DIR}/externals_checks.txt
  prepare_upload_results
fi
