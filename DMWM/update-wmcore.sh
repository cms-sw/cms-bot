#! /bin/sh

if [ ! -d code ]; then
  git clone https://github.com/dmwm/WMCore.git code
fi

pushd code
git pull --rebase origin master
popd
