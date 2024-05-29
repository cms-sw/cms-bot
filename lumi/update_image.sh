#! /bin/bash

OS=$1
ARCH=$2

TAG=$(curl -s "https://hub.docker.com/v2/namespaces/cmssw/repositories/${OS}/tags?page_size=100" | jq -r '.results[].name' | grep "${ARCH}-d" | sort -r | head -n1)
echo "The latest cmssw ${OS} tag is $TAG"
if [ -f cmssw_${OS}:${TAG}.sif ]; then
  echo "Nothing to do"
  exit 0
fi

echo "Building cmssw_${OS}:${TAG}.sif"
singularity build cmssw_${OS}:${TAG}.sif docker://cmssw/${OS}:${TAG}
chmod 644 cmssw_${OS}:${TAG}.sif
ln -s -f cmssw_${OS}:${TAG}.sif cmssw_${OS}.sif
chown -h .project_462000245 cmssw_${OS}:${TAG}.sif cmssw_${OS}.sif
echo "Done"
