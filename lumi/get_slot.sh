#!/bin/bash -ex

echo "[$(date)] Requesting slot on LUMI HPC"

OS=$1
JENKINS_JAR=$2

# work around a problem with the ROCm device permissions
export ROCM_TARGET_LST=${HOME}/.rocm_targets
echo "gfx90a" > ${ROCM_TARGET_LST}

# configure Singularity and CVMFS
export SINGULARITY_CACHEDIR=/project/$SLURM_ACCOUNT/singularity
export SINGULARITY_CMSSWDIR=/project/$SLURM_ACCOUNT/cmssw
export SINGULARITY_PROMPT='[\D{%Y-%m-%d %H:%M:%S}] \[\e]0;\u@\h: \w\a\]\[\033[01;34m\]\u@\h\[\033[00m\]:\[\033[38;5;27m\]\w\[\033[00m\]\$ '
export SINGULARITY_TMPDIR=$TMP/singularity

export SINGULARITY_SCRATCH=/scratch/$SLURM_ACCOUNT/cmsbuild/workspace.ext3
export SINGCVMFS_REPOSITORIES=cms.cern.ch,cms-ib.cern.ch,cms-ci.cern.ch,grid.cern.ch,unpacked.cern.ch,patatrack.cern.ch
export SINGCVMFS_CACHEIMAGE=/project/$SLURM_ACCOUNT/cmsbuild/cvmfscache.ext3

echo "#########################################"

REQUEST_TIME="48:00:00"
REQUEST_PARTITION="small-g"
REQUEST_NODE=1
REQUEST_TASKS=1
REQUEST_CPU=14
REQUEST_GPU=1
REQUEST_MEMORY="60G"

echo "SLURM ACCOUNT: $SLURM_ACCOUNT"

export SINGULARITY_SCRATCH=/scratch/$SLURM_ACCOUNT/cmsbuild/workspace.ext3
export SINGCVMFS_CACHEIMAGE=/project/$SLURM_ACCOUNT/cmsbuild/cvmfscache.ext3

echo "SINGULARITY_SCRATCH: $SINGULARITY_SCRATCH"
echo "SINGULARITY_PROMPT: $SINGULARITY_PROMPT"
echo "SINGULARITY_CACHEDIR: $SINGULARITY_CACHEDIR"

srun --pty --time=$REQUEST_TIME --partition=$REQUEST_PARTITION --hint=multithread --nodes=$REQUEST_NODE \
--ntasks=$REQUEST_TASKS --cpus-per-task=$REQUEST_CPU --gpus=$REQUEST_GPU --mem=$REQUEST_MEMORY \
-- /project/$SLURM_ACCOUNT/cvmfsexec/singcvmfs exec --bind /opt,/project/$SLURM_ACCOUNT,/scratch/$SLURM_ACCOUNT \
--bind $SINGULARITY_SCRATCH:/workspace:image-src=/ --env PS1="$SINGULARITY_PROMPT" "$SINGULARITY_CACHEDIR/cmssw_${OS}.sif" $(dirname $0)/jenkins_java.sh ${JENKINS_JAR}
