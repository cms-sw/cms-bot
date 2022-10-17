#!/bin/bash
name=$1
baseA=$2
baseB=$3
fileN=$4
procN=$5

mkdir -p $name
cd $name
echo "$(date): Will run on ${fileN} in ${name} for ${procN}"
echo -e "gSystem->Load(\"libFWCoreFWLite.so\");\n
         AutoLibraryLoader::enable();\n
         FWLiteEnabler::enable();\n
         gSystem->Load(\"validate_C.so\");\n
         validate(\"${name}\", \"${baseA}/${fileN}\", \"${baseB}/${fileN}\", \"${procN}\");\n
         .qqqqqq" | root -l -b >${name}.log 2>&1
exit_code=$?
[ $exit_code -eq 6 ] && exit_code=0
exit $exit_code
