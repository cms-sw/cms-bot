#! /bin/bash -e

if [ ! -d deployment ]; then
  git clone  https://github.com/dmwm/deployment.git
fi

pushd deployment
git pull --rebase origin master
popd
