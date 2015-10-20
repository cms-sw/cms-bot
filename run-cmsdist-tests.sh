#!/bin/sh -ex

if [ "X$TEST_USER" == X ] || [ "X$TEST_BRANCH" == X ]; then
  echo "Error: TEST_USER and TEST_BRANCH variables must be set"
  exit 1
fi

if [ "X$ARCH" == X ]; then
  ARCH="slc6_amd64_gcc493"
fi

if [ "X$CMSDIST_BRANCH" == X ]; then
  CMSDIST_BRANCH="IB/CMSSW_8_0_X/stable"
fi

if [ "X$PKGTOOLS_BRANCH" == X ]; then
  PKGTOOLS_BRANCH="V00-22-XX"
fi

BUILD_DIR="testBuildDir"

git clone git@github.com:cms-sw/cmsdist CMSDIST -b $CMSDIST_BRANCH
git clone git@github.com:cms-sw/pkgtools PKGTOOLS -b $PKGTOOLS_BRANCH

pushd CMSDIST
git pull git://github.com/$TEST_USER/cmsdist.git $TEST_BRANCH
# Check which packages the PR changes
PKGS=$(git diff  ..origin/$CMSDIST_BRANCH --name-only | cut -d"." -f"1")

# Check if the packages have a toolfile and add them to the build if they exists
for P in $PKGS; do
  if [ -f $P-toolfile.spec ]; then
    TOOLFILES=$TOOLFILES" "$P-toolfile
  fi
done
popd

# Build the packages
PKGTOOLS/cmsBuild -i $BUILD_DIR --arch $ARCH -j 12 build $PKGS $TOOLFILES

# Create an appropriate CMSSW area
CMSSW_IB=$(scram l $(echo $CMSDIST_BRANCH | cut -d"/" -f 2) | grep -v /ReleaseCandidates | tail -n 1 | awk '{print $2}')
SCRAM_ARCH=$ARCH
scram project $CMSSW_IB
pushd $CMSSW_IB/src
eval $(scramv1 runtime -sh)

# Setup all the toolfiles previously built
for TOOL in $TOOLFILES; do
  scram setup ../../$BUILD_DIR/$ARCH/external/$TOOL/*/etc/scram.d/*.xml
done
eval $(scramv1 runtime -sh)

# Search for CMSSW package that might depend on the compiled externals
CMSSW_DEP=$(for P in $PKGS; do (for L in $(scram build echo_${P}_USED_BY); do echo $L | grep '\(self\|cmssw\)' | cut -d"/" -f 2,3; done); done)
for DEP in $CMSSW_DEP; do git cms-addpkg $DEP; done

# If there is a CMSSW PR to check alongside merge it
if [ "X$CMSSW_PR" != X ]; then
  git cms-merge-topic $CMSSW_PR
fi

# Build all the packages added
scram build -j 12
