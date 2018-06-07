#!/bin/bash -e
WF_PATH=$1
DES_PATH=$2
if [ ! -d "${WF_PATH}" ] ; then echo "ERROR: Filter failed comparison: No such directory: ${WF_PATH}"; exit 1 ; fi
if [ ! -d "${DES_PATH}" ] ; then echo "ERROR: Filter failed comparison: No such directory: ${DES_PATH}"; exit 1 ; fi
WF_DIR=$(basename "${WF_PATH}")
while read html ; do
  if [ $(grep 'Skipped:\|Null:\|Fail:' "${html}" | wc -l) -gt 0 ] ; then
    [ -d "${DES_PATH}/${WF_DIR}" ] || mkdir -p "${DES_PATH}/${WF_DIR}"
    mv "${html}" "${DES_PATH}/${WF_DIR}"
  fi
done < <(find  ${WF_PATH}  -name '*.html')
if [ -d "${DES_PATH}/${WF_DIR}" ] ; then
  while read png ; do
    mv "${png}" "${DES_PATH}/${WF_DIR}"
  done < <(find  ${WF_PATH} -name "*.png")
  echo "Matched Skip/Null/Fail: ${WF_DIR}"
else
  echo "All clean: ${WF_DIR}"
fi
