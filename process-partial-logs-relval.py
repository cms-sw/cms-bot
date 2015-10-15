#!/usr/bin/env python
import os, sys
from runPyRelValThread import PyRelValsThread

path=sys.argv[1]
ProcessLogs = PyRelValsThread(1,path)
print "Generating runall log file"
ProcessLogs.update_runall()
print "Parsing logs for workflows/steps"
ProcessLogs.parseLog()
newloc = os.path.dirname(path) + '/pyRelValMatrixLogs/run'

os.system('mkdir -p ' + newloc)
os.system('mv ' + path + '/runall-report-step123-.log '+ newloc)
os.system('mv ' + path + '/runTheMatrixMsgs.pkl '+ newloc)
cmd = 'cd '+path+'; rm -f ../pyRelValMatrixLogs.zip ; zip -r ../pyRelValMatrixLogs.zip .'
print "Running ",cmd
os.system(cmd)
print "Done"




