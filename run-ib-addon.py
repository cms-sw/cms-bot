#! /usr/bin/env python
from sys import exit
from os import environ
from cmsutils import cmsRunProcessCount, doCmd
from logUpdater import LogUpdater

if (not environ.has_key("CMSSW_BASE")) or (not environ.has_key("SCRAM_ARCH")):
  print "ERROR: Unable to file the release environment, please make sure you have set the cmssw environment before calling this script"
  exit(1)

logger = LogUpdater(environ["CMSSW_BASE"])
ret = doCmd('cd '+environ["CMSSW_BASE"]+'; rm -rf addOnTests; timeout 5400 addOnTests.py -j '+str(cmsRunProcessCount)+' 2>&1 >addOnTests.log ')
doCmd('cd '+environ["CMSSW_BASE"]+'/addOnTests/logs; zip -r addOnTests.zip *.log')
logger.updateAddOnTestsLogs()

