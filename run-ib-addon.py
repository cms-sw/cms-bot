#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function
from sys import exit, argv
from os import environ
from cmsutils import cmsRunProcessCount, doCmd
from logUpdater import LogUpdater

if ("CMSSW_BASE" not in environ) or ("SCRAM_ARCH" not in environ):
    print(
        "ERROR: Unable to file the release environment, please make sure you have set the cmssw environment before calling this script"
    )
    exit(1)

timeout = 7200
try:
    timeout = int(argv[1])
except:
    timeout = 7200
logger = LogUpdater(environ["CMSSW_BASE"])
ret = doCmd(
    "cd %s; rm -rf addOnTests; timeout %s addOnTests.py -j %s 2>&1 >addOnTests.log"
    % (environ["CMSSW_BASE"], timeout, cmsRunProcessCount)
)
doCmd("cd " + environ["CMSSW_BASE"] + "/addOnTests/logs; zip -r addOnTests.zip *.log")
logger.updateAddOnTestsLogs()
