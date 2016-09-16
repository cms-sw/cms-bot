#!/bin/sh -ex
cd $WORKSPACE

CONFIG_MAP_PATH="$WORKSPACE/cms-bot/config.map"
RELEASE_FILTER=${RELEASE_FILTER-.*}
ARCHITECTURE_FILTER=${ARCHITECTURE_FILTER-.*}
RELEASE_QUEUES="`cat $CONFIG_MAP_PATH | grep -v "DISABLED=" | grep -e \"SCRAM_ARCH=$ARCHITECTURE_FILTER;\" | grep -e \"RELEASE_QUEUE=$RELEASE_FILTER;\" | sed -e's/.*RELEASE_QUEUE=//;s/;.*//' | sort -u`"

if [ "X$RELEASE_QUEUES" = X ]; then
  echo No releases found to build.
  exit 1
fi

for QUEUE in $RELEASE_QUEUES; do
  unset RELEASE_BRANCH
  eval `cat $CONFIG_MAP_PATH | grep -v "DISABLED=" | grep "RELEASE_QUEUE=$QUEUE;"`
  RELEASE_BRANCH=${RELEASE_BRANCH-$RELEASE_QUEUE} 
  RELEASE_NAME=`date +${QUEUE}_${DATE}`
  $WORKSPACE/cms-bot/tag-ib $DRY_RUN --branch ${QUEUE} --date ${DATE} --tag ${RELEASE_NAME} || continue

  RELEASE_LIST="`git show --pretty='%d' HEAD | tr '[ ,()]' '[\n   ]'| { grep \"^${QUEUE}_20\" || true; }`"

  for ARCH_CONFIG in `cat $CONFIG_MAP_PATH | grep -v "DISABLED=" | grep "RELEASE_QUEUE=$QUEUE;" | grep "SCRAM_ARCH=$ARCHITECTURE_FILTER;"`; do
    DOCKER_IMG=
    eval $ARCH_CONFIG
    echo "RELEASE_NAME=$RELEASE_NAME" > $WORKSPACE/properties-$RELEASE_NAME-$SCRAM_ARCH.txt
    echo "DATE_FORMAT=$DATE" >> $WORKSPACE/properties-$RELEASE_NAME-$SCRAM_ARCH.txt
    echo "REPOSITORY=cms.${CMS_REPOSITORY}" >> $WORKSPACE/properties-$RELEASE_NAME-$SCRAM_ARCH.txt
    echo "RELEASE_QUEUE=${QUEUE}" >> $WORKSPACE/properties-$RELEASE_NAME-$SCRAM_ARCH.txt
    echo "ARCHITECTURE=${SCRAM_ARCH}" >> $WORKSPACE/properties-$RELEASE_NAME-$SCRAM_ARCH.txt
    echo "DOCKER_IMG=${DOCKER_IMG}"  >> $WORKSPACE/properties-$RELEASE_NAME-$SCRAM_ARCH.txt
    if [ "X$ALWAYS_BUILD" = X ]; then
      echo "RELEASE_LIST=`echo ${RELEASE_LIST} | tr \\n \\ `" >> $WORKSPACE/properties-$RELEASE_NAME-$SCRAM_ARCH.txt
    else
      echo "RELEASE_LIST=" >> $WORKSPACE/properties-$RELEASE_NAME-$SCRAM_ARCH.txt
    fi
  done
done

ls $WORKSPACE

# Delete all files after having created them so that we do not build unless
# requested.
if [ "X$SCHEDULE_BUILDS" = Xfalse ]; then
  mkdir -p $WORKSPACE/not-scheduled
  touch $WORKSPACE/properties-x.txt
  mv $WORKSPACE/properties-*.txt $WORKSPACE/not-scheduled
fi
