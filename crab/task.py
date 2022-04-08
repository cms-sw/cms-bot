from CRABClient.UserUtilities import config
import os, re, time

archs       = os.environ['SCRAM_ARCH'].split("_")
requestName = os.getenv('CRAB_REQUEST', str(int(time.time())))
numJobs     = int(os.getenv('CRAB_JOBS',2))

SingularityImage = '/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel%s-itb' % re.sub('[a-z]', '', archs[0])
if 'SINGULARITY_IMAGE' in os.environ:
  SingularityImage = os.environ['SINGULARITY_IMAGE']

config = config()
config.Data.unitsPerJob                = int(os.getenv('JOB_EVENTS', 1))
config.General.instance                = os.getenv('CRABCONFIGINSTANCE','prod')
config.General.workArea                = 'crab_projects'
config.General.requestName             = requestName
config.JobType.pluginName              = 'PrivateMC'
config.JobType.psetName                = os.path.join(os.path.dirname(__file__), 'pset.py')
config.Data.splitting                  = 'EventBased'
config.Data.totalUnits                 = config.Data.unitsPerJob * numJobs
config.Data.publication                = False
config.Site.storageSite                = 'T2_CH_CERN'
config.JobType.allowUndistributedCMSSW = True

if 'CRAB_SCHEDD_NAME' in os.environ:
  config.Debug.scheddName = os.environ['CRAB_SCHEDD_NAME']
if 'CRAB_COLLECTOR' in os.environ:
  config.Debug.collector = os.environ['CRAB_COLLECTOR']

config.Debug.extraJDL     = ['+SingularityImage="%s"' % SingularityImage]
config.Debug.extraJDL.append('+DESIRED_Archs="%s"' % 'X86_64' if ('amd64' == archs[1]) else archs[1])
if 'CRAB_SITE' in os.environ:
  config.Debug.extraJDL.append('+DESIRED_Sites="%s"' % os.environ['CRAB_SITE'])

