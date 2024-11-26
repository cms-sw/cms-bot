#!/bin/bash -ex

echo "[$(date)] Requesting slot on LUMI HPC"

OS=$1
USER=$2
NODE_NAME=$3
JENKINS_JAR=$4
export SLURM_ACCOUNT=$5

# CMS config
export CMS_SITE_OVERRIDE=T2_FI_HIP
export ARTIFACTS_USER=${USER}

# set up the project number
export SBATCH_ACCOUNT=$SLURM_ACCOUNT
export SALLOC_ACCOUNT=$SLURM_ACCOUNT

# set up the project directories
export PROJECT=/project/$SLURM_ACCOUNT
export SCRATCH=${PROJECT}/$USER/$SESSION
mkdir -p $SCRATCH

# disable automatic re-queueing of jobs on failed nodes
export SBATCH_NO_REQUEUE=1

export SINGULARITY_CACHEDIR=/project/$SLURM_ACCOUNT/singularity

export SINGULARITY_SCRATCH=$SCRATCH/workspace.ext3
if ! [ -f $SINGULARITY_SCRATCH ]; then
  mkdir -p $(dirname $SINGULARITY_SCRATCH)
  /usr/sbin/mkfs.ext3 -m 0 -E root_owner $SINGULARITY_SCRATCH 100G
fi

export SINGCVMFS_CACHEIMAGE=$SCRATCH/cvmfscache.ext3
if ! [ -f $SINGCVMFS_CACHEIMAGE ]; then
  mkdir -p $(dirname $SINGCVMFS_CACHEIMAGE)
  /usr/sbin/mkfs.ext3 -m 0 -E root_owner $SINGCVMFS_CACHEIMAGE 50G
fi

export KRB5CCNAME=FILE:$SCRATCH/krb5cc_${USER}_${NODE_NAME}
klist || true

echo "#########################################"

REQUEST_TIME="48:00:00"
REQUEST_PARTITION="small-g"
REQUEST_NODE=1
REQUEST_TASKS=1
REQUEST_CPU=14
REQUEST_GPU=1
REQUEST_MEMORY="60G"

echo "SLURM ACCOUNT: $SLURM_ACCOUNT"
echo "SINGULARITY_SCRATCH: $SINGULARITY_SCRATCH"
echo "SINGULARITY_CACHEDIR: $SINGULARITY_CACHEDIR"

${PROJECT}/local/bin/cms-${OS}-exec --bind $SINGULARITY_SCRATCH:/workspace:image-src=/ $(dirname $0)/jenkins_java.sh ${JENKINS_JAR}
