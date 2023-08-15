#!/usr/bin/env python3
from sys import argv
from logUpdater import LogUpdater
logger=LogUpdater(dirIn=argv[1])
logger.copyLogs(argv[2])
