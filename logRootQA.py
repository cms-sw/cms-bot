#!/usr/bin/env python

from os import listdir
from os.path import isfile, join
import os
import subprocess
import sys

def getFiles(d,ending):
    return [os.path.join(dp, f) for dp, dn, filenames in os.walk(d) for f in filenames if os.path.splitext(f)[1] == '.'+ending]
#    return  [ f for f in listdir(d) if isfile(join(d,f)) ]

def getCommonFiles(d1,d2,ending):
    l1=getFiles(d1,ending)
    l2=getFiles(d2,ending)
    common=[]
    for l in l1:
        lT=l[len(d1):]
        if d2+lT in l2:
            common.append(lT)
    return common

def checkLines(l1,l2):
    lines=0
    for l in open(l2):
        lines=lines+1
    for l in open(l1):
        lines=lines-1
    if lines>0:
        print "You added "+str(lines)+" to "+l2
    if lines<0:
        print "You removed "+str(-1*lines)+" to "+l2
        
    return lines

import subprocess as sub

def runCommand(c):
    p=sub.Popen(c,stdout=sub.PIPE,stderr=sub.PIPE)
    output=p.communicate()
    return output

def checkEventContent(r1,r2):
    retVal=True

    output1=runCommand(['ls','-l',r1])
    output2=runCommand(['ls','-l',r2])
    s1=output1[0].split()[4]
    s2=output2[0].split()[4]
    if abs(float(s2)-float(s1))>0.1*float(s1):
        print "Big output file size change?",s1,s2
        retVal=False

    output1=runCommand(['edmEventSize','-v',r1])
    output2=runCommand(['edmEventSize','-v',r2])

    if 'contains no' in output1[1] and 'contains no' in output2[1]:
        w=1
    else:
        sp=output1[0].split('\n')
        p1=[]
        for p in sp:
            if len(p.split())>0:
                p1.append(p.split()[0])
        sp=output2[0].split('\n')
        p2=[]
        for p in sp:
            if len(p.split())>0:
                p2.append(p.split()[0])

        common=[]    
        for p in p1:
            if p in p2: common.append(p)
        if len(common)!=len(p1) or len(common)!=len(p2):
            print 'Change in products found in',r1
            for p in p1:
                if p not in common: print '    Product missing '+p
            for p in p2:
                if p not in common: print '    Product added '+p
            retVal=False    
    return retVal

##########################################
#
#
#
qaIssues=False

baseDir='CMSSW_7_6_X_2015-08-04-2300'
testDir='PR-10504'
if len(sys.argv)==3:
    baseDir=sys.argv[1]
    testDir=sys.argv[2]

commonLogs=getCommonFiles(baseDir,testDir,'log')

#### check the printouts
lines=0
lChanges=False
for l in commonLogs:
    lCount=checkLines(baseDir+l,testDir+l)
    lines=lines+lCount
    if lChanges!=0:
        lChanges=True

if lines >0 :
    print "You added "+str(lines)+" lines to the logs" 
if lChanges:
    qaIssues=True

#### compare edmEventSize on each to look for new missing candidates
commonRoots=getCommonFiles(baseDir,testDir,'root')
sameEvts=True
for r in commonRoots:
    sameEvts=sameEvts and checkEventContent(baseDir+r,testDir+r)

if not sameEvts:
    qaIssues=True

#### conclude
if not qaIssues:
    print "No potential problems in log/root QA checks!"
