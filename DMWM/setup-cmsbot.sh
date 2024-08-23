#! /bin/bash -e

# For reference only, you cannot actually run this script because it has not run yet

set -x

start=`date +%s`

rm -rf cms-bot || true
if [ ! -d cms-bot ]; then
  git clone https://github.com/$CMS_BOT_REPO/cms-bot
fi

pushd $WORKSPACE/cms-bot/

wget https://pypi.python.org/packages/source/r/requests/requests-2.3.0.tar.gz#md5=7449ffdc8ec9ac37bbcd286003c80f00
tar -xvf requests-2.3.0.tar.gz
rm -rf requests || true
mv requests-2.3.0/requests/ requests

git checkout $CMS_BOT_BRANCH
git pull --rebase origin $CMS_BOT_BRANCH

popd

end=`date +%s`
runtime=$((end-start))
echo "Total time to setup cms-bot: $runtime"
