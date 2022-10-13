#!/usr/bin/env python
from __future__ import print_function
from hashlib import sha1
import os , re , sys , json
import xml.etree.ElementTree as ET
from es_utils import send_payload,get_payload,resend_payload,get_payload_wscroll
JENKINS_PREFIX="jenkins"
try:    JENKINS_PREFIX=os.environ['JENKINS_URL'].strip("/").split("/")[-1]
except: JENKINS_PREFIX="jenkins"

def findParametersAction(root):
  if root.tag=='parameters': return root
  for x in root:
    p=findParametersAction(x)
    if p is not None: return p
  return None

def getParameters(root, payload):
  n=root.find('name')
  if n is not None:
    if n.text is None: return
    v=root.find('value')
    vv = "None"
    if v is not None: vv = str(v.text)
    payload['parameter_'+n.text]=vv
  else:
    for x in root: getParameters(x, payload)

query_running_builds = """{
"query": {"bool": {"must": {"query_string": {"query": "job_status:Running AND jenkins_server:%s", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}""" % JENKINS_PREFIX

all_local = []
path = '/build/builds'
document = "builds-data"
rematch = re.compile(".*/\d+$")
for root, dirs, files in os.walk(path):
  if rematch.match(root):
    logFile = root + '/build.xml'
    flagFile = root + '/check.done'
    if os.path.exists(logFile) and not os.path.exists(flagFile):
      payload = {}
      job_info = root.split('/')
      payload['job_name'] = '/'.join(job_info[3:-1])
      payload['build_number'] = job_info[-1]
      payload['url'] = "https://cmssdt.cern.ch/"+JENKINS_PREFIX+"/job/" + '/job/'.join(job_info[3:-1]) + "/" + job_info[-1] + "/"
      id = sha1(JENKINS_PREFIX+":"+root).hexdigest()
      try:
        tree = ET.parse(logFile)
        root = tree.getroot()
        pa=findParametersAction(root)
        if pa is not None: getParameters(pa, payload)
        jstime = root.find('startTime').text
        payload['@timestamp'] = int(jstime)
        payload['slave_node'] = root.find('builtOn').text
        payload['jenkins_server'] = JENKINS_PREFIX
        build_result = root.find('result')
        if build_result is not None:
          payload['build_result'] = build_result.text
          payload['build_duration'] = int(int(root.find('duration').text)/1000)
          payload['job_status'] = 'Finished'
          os.system('touch "' + flagFile + '"')
        else:
          payload['job_status'] = 'Running'
        all_local.append(id)
        weekindex="jenkins-jobs-"+str(int((((int(jstime)/1000)/86400)+4)/7))
        print("==>",id,payload['job_name'],payload['build_number'],payload['job_status'])
        send_payload(weekindex,document,id,json.dumps(payload))
      except Exception as e:
        print("Xml parsing error",logFile , e)
running_builds_elastic={}
content_hash = get_payload_wscroll('jenkins-*',query_running_builds)
if not content_hash:
  running_builds_elastic = {}
else:
  if (not 'hits' in content_hash) or (not 'hits' in content_hash['hits']):
    print("ERROR: ",content)
    sys.exit(1)
  print("Found:", len(content_hash['hits']['hits']))
  for hit in content_hash['hits']['hits']:
    if hit["_index"].startswith("cmssdt-jenkins-jobs-"):
      if not "jenkins_server" in hit["_source"]: hit["_source"]["jenkins_server"] = JENKINS_PREFIX
      if hit["_source"]["jenkins_server"]!=JENKINS_PREFIX: continue
      try:print("Running:",hit["_source"]["jenkins_server"],":",hit["_source"]['job_name'],hit["_source"]['build_number'],hit["_index"],hit['_id'])
      except Exception as e: print("Error:", e)
      running_builds_elastic[hit['_id']]=hit
for build in running_builds_elastic:
  if build not in all_local:
    hit = running_builds_elastic[build]
    hit["_source"]["job_status"]="Failed"
    resend_payload(hit)
    print("job status marked as Failed")

