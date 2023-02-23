### RPM cms cmssw-fake-package 1.0
## NOCOMPILER
## NO_VERSION_SUFFIX

@provides@

%prep
%build
%install
echo 'This is a fake package providing everything that CMSSW provides'> %{i}/README
