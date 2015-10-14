#!/usr/bin/env python
import os, sys, glob, re, shutil, time, threading
from commands import getstatusoutput
import cmd
from runPyRelValThread import PyRelValsThread

path=sys.argv[1]
ProcessLogs = PyRelValsThread(1,path)
ProcessLogs.update_runall()
ProcessLogs.parseLog()
newloc = os.path.dirname(path) + '/pyRelValMatrixLogs/run'

os.system('mkdir -p ' + newloc)
os.system('mv ' + path + '/runall.log '+ newloc)
os.system('mv ' + path + '/runall-report-step123-.log '+ newloc)
os.system('mv ' + path + '/runTheMatrixMsgs.pkl '+ newloc)
cmd = 'rm -rf pyRelValMatrixLogs.zip ; ' + 'cd ' + path + ' ; ' + 'zip -rq ../pyRelValMatrixLogs.zip .'
os.system(cmd)




