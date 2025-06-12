#!/bin/bash
cuda_dir=""
for dir in $(echo $LD_LIBRARY_PATH | tr : '\n' | grep -v '^$') ; do
  [ -e ${dir}/libcudart.so ] || continue
  cuda_dir=$dir
  break
done

if [ "${cuda_dir}" != "" ] ; then
  opts=""
  opts="-B ${cuda_dir}:${cuda_dir} --env LD_LIBRARY_PATH=${cuda_dir}"
  for ml in $(ls /usr/lib64/libnvidia-ml.so*) ; do
    opts="-B $ml:$ml ${opts}"
  done
  echo "$opts"
fi
