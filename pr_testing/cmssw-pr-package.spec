### RPM cms cmssw-pr-package 1.0
## NOCOMPILER
## NO_VERSION_SUFFIX

Source: none

## INCLUDE cmssw-pr-provides
## INCLUDE cmssw-pr-defines

%prep

%build

%install
mkdir -p %{i}/bin
mkdir -p %{i}/lib
mkdir -p %{i}/biglib

cp -r %{release_dir}/{bin,lib,biglib} %{i}/
