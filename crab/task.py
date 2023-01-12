from CRABClient.UserUtilities import config
import os, re, time

archs      = os.environ['SCRAM_ARCH'].split("_")
osMajorVer = int(re.sub('[a-z]', '', archs[0]))

config = config()
config.General.instance                = os.getenv('CRABCONFIGINSTANCE','prod')
config.General.requestName             = os.getenv('CRAB_REQUEST', str(int(time.time())))
config.General.transferOutputs         = True
config.General.transferLogs            = False

config.Data.unitsPerJob                = 10
config.Data.totalUnits                 = 10
config.Data.splitting                  = 'EventBased'
config.Data.publication                = False

config.JobType.psetName                = os.path.join(os.path.dirname(__file__), 'pset.py')
config.JobType.pluginName              = 'PrivateMC'
config.JobType.maxJobRuntimeMin        = 60
config.JobType.maxMemoryMB             = 2000
config.JobType.allowUndistributedCMSSW = True

config.Site.storageSite                = 'T2_CH_CERN'

if 'CRAB_SCHEDD_NAME' in os.environ and os.environ['CRAB_SCHEDD_NAME']!='':
  config.Debug.scheddName = os.environ['CRAB_SCHEDD_NAME']
if 'CRAB_COLLECTOR' in os.environ and os.environ['CRAB_COLLECTOR']!='':
  config.Debug.collector = os.environ['CRAB_COLLECTOR']

config.Debug.extraJDL     = ['+REQUIRED_OS="rhel%s"'  % 7 if osMajorVer>6 else 6]
if 'amd64' == archs[1]:
  config.Debug.extraJDL.append('+DESIRED_Archs="%s"'    % 'X86_64' if ('amd64' == archs[1]) else archs[1])
if 'SINGULARITY_IMAGE' in os.environ and os.environ['SINGULARITY_IMAGE']!='':
  config.Debug.extraJDL.append('+SingularityImage="%s"' % os.environ['SINGULARITY_IMAGE'])
if 'CRAB_SITE' in os.environ and os.environ['CRAB_SITE']!='':
  config.Debug.extraJDL.append('+DESIRED_Sites="%s"' % os.environ['CRAB_SITE'])
