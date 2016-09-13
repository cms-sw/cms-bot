#!/bin/bash -ex

PUSH_CHANGES=$1
JENKINS_DIR="/var/lib/jenkins"
JENKINS_VERSION=$(java -jar ${JENKINS_DIR}/jenkins-cli.jar -s http://localhost:8080/jenkins/ version)
[ "X$JENKINS_VERSION" = "X" ] && exit 1
rm -rf cmsjenkins
git clone https://:@gitlab.cern.ch:8443/cms-sw/cmsjenkins.git cmsjenkins
pushd cmsjenkins
  if [ $(git branch -a | grep " remotes/origin/cms-$JENKINS_VERSION"'$' | wc -l) -eq 0 ] ; then
    git checkout -b cms-$JENKINS_VERSION
  else
    git checkout -f cms-$JENKINS_VERSION
  fi
  git config --global user.name "CMS Build"
  git config --global user.email "cmsbuild@cern.ch"

  IFS=$'\n' 
  for xml in $(find ${JENKINS_DIR} -name '*.xml' -type f | sed "s|^${JENKINS_DIR}/||" | grep -v ^config-history/ | grep -v ^war/ | grep -v ^plugins/ | grep -v ^fingerprints/ | grep -v ^global-build-stats/ | grep -v /builds/); do
    dir=$(dirname "$xml")
    mkdir -p "./${dir}"
    cp -pf "${JENKINS_DIR}/${xml}" "./${xml}"
  done
 
  for xml in $(find . -name '*' -type f | grep -v /.git/ | sed "s|^./||" | sort ) ; do
    [ -e "${JENKINS_DIR}/${xml}" ] || rm -f "${xml}"
  done
  for dir in $(find . -type d | sed "s|^./||" | sort -r) ; do
    [ $(find ${dir} -type f | wc -l) -gt 0 ] && continue
    rm -rf ${dir}
  done
  git add . || true
  git commit -a -m 'Updates new configurations' || true
  if [ "X$PUSH_CHANGES" = "Xpush" ] ; then
    [ $(git diff origin/cms-${JENKINS_VERSION} --name-only | wc -l) -gt 0 ] && git push origin cms-${JENKINS_VERSION}
  fi
popd
rm -rf cmsjenkins


