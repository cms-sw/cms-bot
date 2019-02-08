#!/usr/bin/env python
from os import environ
from sys import argv
from logUpdater import LogUpdater
logger=LogUpdater(dirIn=environ["CMSSW_BASE"])
logger.copyLogs(argv[1])
