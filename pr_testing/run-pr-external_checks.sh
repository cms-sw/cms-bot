#!/bin/bash -e
source $(dirname $0)/setup-pr-test-env.sh
toolconf_file=$CMSSW_BASE/config/toolbox/$SCRAM_ARCH/tools/selected/python-paths.xml
[ -f $toolconf_file ] || exit 0
tool_conf=$(grep -E '/cms/cmssw-(patch-|)tool-conf/' $toolconf_file | tr ' ' '\n' | grep -E '/cmssw-(patch-|)tool-conf/' | sed 's|.*=||;s|"||g' | rev  | cut -d/ -f4- | rev)
tool_pkg=$(echo $tool_conf | rev | cut -d/ -f1-3 | rev | tr '/' '+')
base_dir=$(echo $tool_conf | sed "s|/$SCRAM_ARCH/.*||")
cmspkg="${base_dir}/common/cmspkg -a $SCRAM_ARCH"
deps=$(${cmspkg} env -- rpm -q --requires ${tool_pkg} | tr '\n' ' ')
LOGFILE=$WORKSPACE/externals-checks.log
if [ -f ${base_dir}/$SCRAM_ARCH/${tool_pkg}.log ] ; then
  grep "${base_dir}/${SCRAM_ARCH}/" ${base_dir}/$SCRAM_ARCH/${tool_pkg}.log | grep -i ': No such file or directory' > ${WORKSPACE}/externals-checks-missing.log || true
fi
rm -f $LOGFILE ; touch $LOGFILE
echo "Looking in to ${tool_conf} ${tool_pkg} with base dir ${base_dir}"
for init in $(find ${base_dir}/${SCRAM_ARCH} -path '*/etc/profile.d/init.sh') ; do
  pkg_dir=$(echo $init | sed 's|/etc/profile.d/init.sh||')
  pkg=$(echo $pkg_dir | sed "s|$base_dir/$SCRAM_ARCH/||;s|/|+|g")
  echo "Checking: $pkg $pkg_dir"
  [ $(echo " ${deps} " | grep " ${pkg} "| wc -l) -gt 0 ] || continue
  build_dir=$(${cmspkg} env -- rpm -q --scripts $pkg | grep '/tmp/BUILDROOT/' | head -1 | sed 's|/tmp/BUILDROOT/.*||;s|^[^/]*/|/|')
  [ "${build_dir}" != "" ] || continue
  echo "=====> Search ${pkg_dir}" >> $LOGFILE
  grep "${build_dir}/" -Ir ${pkg_dir} >${WORKSPACE}/match.data 2>&1 || true
  if [ -f ${WORKSPACE}/externals-checks-missing.log ] ; then
    grep "${pkg_dir}" ${WORKSPACE}/externals-checks-missing.log >> ${WORKSPACE}/match.data || true
  fi
  FOUND=$(cat ${WORKSPACE}/match.data |wc -l)
  if [ $FOUND -gt 0 ] ; then
    cat ${WORKSPACE}/match.data
    cat ${WORKSPACE}/match.data >> $LOGFILE
  fi
done
rm -f ${WORKSPACE}/match.data
if [ "${DRY_RUN}" = "" ] ; then
  echo 'CMSSWTOOLCONF_CHECKS;OK,Externals path checks,See Log,externals-checks.log' >> ${RESULTS_DIR}/externals.txt
  prepare_upload_results
fi
