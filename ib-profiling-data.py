#!/bin/env python3
import sys
import site
import os
import json
import time
from itertools import islice
from CMSMonitoring.StompAMQ import StompAMQ

def splitall(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path: # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts
    
def IB2ts(release):
  from datetime import datetime
  rel_msec  = int(datetime.strptime(release.split("_")[-1], '%Y-%m-%d-%H%M',).strftime('%s')) * 1000
  return rel_msec

def IB2relq(release):
    if "_X_" in release:
        release_queue = release.split("_X_",1)[0]+"_X"
    else:
        release_queue = "_".join(release.split("_")[:3])+"_X"
    return release_queue
    
username = ""
password = ""
producer = "cms-cmpwg"
topic = "/topic/cms.cmpwg"
host = "cms-mb.cern.ch"
port = 61323
cert = "%s/.globus/usercert.pem" % os.getenv("HOME")
ckey = "%s/.globus/userkey.pem" % os.getenv("HOME")
stomp_amq = StompAMQ(username, password, producer, topic, key=ckey, cert=cert, validation_schema=None, host_and_ports=[(host, port)])
stomp_amq.connect()

with open('%s/profiling/packages.json' % os.getenv("WORKSPACE"), 'r') as file:
    packages=json.load(file)

import re
compiled=[]
for key in packages.keys():
    if '|' in key:
        [t,l]=key.split('|')
        t=re.compile(t)
        l=re.compile(l)
    else:
        t=None
        l=re.compile(key)
    compiled.append([t,l,packages[key]])

def findGroup(data):
    unassigned=[]
    assigned=False
    group='Unassigned|Unassigned'
    for [t,l,g] in compiled:
        if re.match(t,data['module_type']) and re.match(l,data['module_label']):
            assigned=True
            group=g
            break
    return group.split('|')

import glob
import hashlib
documents=[]
for f in glob.glob('%s/upload/*/*/*cpu*.json' % os.getenv("WORKSPACE")):
        print(f)
        with open(f,'r') as file:
                dirs=splitall(f)
                data=json.load(file)
                total=data.get("total")
                payload={}
                payload["module_label"]=str(total.get("label","no label"))
                payload["module_type"]=str(total.get("type","no type"))
                [subsystem,package]=findGroup(payload)
                payload["module_package"]=str(package)
                payload["module_subsystem"]=str(subsystem)
                payload[str(payload["module_type"])]=str(payload["module_label"])
                payload["events"]=int(total.get("events", 0))
                payload["time_thread"]=float(total.get("time_thread",0.))
                payload["time_real"]=float(total.get("time_real",0.))
                payload["mem_alloc"]=int(total.get("mem_alloc",0))
                payload["mem_free"]=int(total.get("mem_free",0))
                release=str(os.getenv("RELEASE_FORMAT"))
                arch=str(os.getenv("ARCHITECTURE"))
                workflow=str(dirs[-2])
                release_queue=str(IB2relq(release))
                release_ts=int(IB2ts(release))
                str2hash=release+arch+workflow+str(release_ts)+payload.get("module_label")
                rhash=hashlib.sha1(str2hash.encode()).hexdigest()
                payload["release"]=release
                payload["release_queue"]=release_queue
                payload["release_ts"]=release_ts
                payload["workflow"]=workflow
                payload["arch"]=arch
                payload["hash"]=rhash
                notification, _, _ = stomp_amq.make_notification(payload,"profiling_document",dataSubfield=None)
                documents.append(notification)
                modules=data.get("modules")
                for module in modules:
                    mpayload={}
                    mpayload["module_type"]=str(module.get("type","no type"))
                    mpayload["module_label"]=str(module.get("label","no label"))
                    [subsystem,package]=findGroup(mpayload)
                    mpayload["module_package"]=str(package)
                    mpayload["module_subsystem"]=str(subsystem)
                    mpayload[str(payload["module_type"])]=str(payload["module_label"])
                    mpayload["events"]=int(module.get("events", 0))
                    mpayload["time_thread"]=float(module.get("time_thread",0.))
                    mpayload["time_real"]=float(module.get("time_real",0.))
                    mpayload["mem_alloc"]=int(module.get("mem_alloc",0))
                    mpayload["mem_free"]=int(module.get("mem_free",0))
                    mpayload["release"]=release
                    mpayload["release_queue"]=release_queue
                    mpayload["release_ts"]=release_ts
                    mpayload["workflow"]=workflow
                    mpayload["arch"]=arch
                    str2hash=release+arch+workflow+str(release_ts)+mpayload.get("module_label")
                    mhash=hashlib.sha1(str2hash.encode()).hexdigest()
                    mpayload["hash"]=mhash
                    notification, _, _ = stomp_amq.make_notification(mpayload,"profiling_document",dataSubfield=None)
                    documents.append(notification)

#print(documents)
results=stomp_amq.send(documents)
#print(results)
