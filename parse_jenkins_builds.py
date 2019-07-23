#!/usr/bin/env python
from __future__ import print_function
from hashlib import sha1
import os , re , sys , json
import xml.etree.ElementTree as ET
from es_utils import send_payload,get_payload,resend_payload
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
"query": {"bool": {"must": {"query_string": {"query": "job_status:running"}}}},
"from": 0,
"size": 10000
}"""

all_local = list() 
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
      payload['job_name'] = job_info[3]
      payload['build_number'] = job_info[-1]
      payload['url'] = "https://cmssdt.cern.ch/"+JENKINS_PREFIX+"/job/" + job_info[3] + "/" + job_info[-1] + "/"
      id = sha1(root).hexdigest()
      try:
        tree = ET.parse(logFile)
        root = tree.getroot()
        pa=findParametersAction(root)
        if pa is not None: getParameters(pa, payload)
        jstime = root.find('startTime').text
        payload['@timestamp'] = int(jstime)
        payload['slave_node'] = root.find('builtOn').text
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
        print(payload)
        send_payload(weekindex,document,id,json.dumps(payload))
      except Exception as e:
        print("Xml parsing error",logFile , e)
running_builds_elastic={}
content = get_payload('jenkins-*',query_running_builds)
if content == "":
  running_builds_elastic = []
else:
  content_hash = json.loads(content)
  if (not 'hits' in content_hash) or (not 'hits' in content_hash['hits']):
    print("ERROR: ",content)
    sys.exit(1)
  for hit in content_hash['hits']['hits']:
    if hit["_index"].startswith("jenkins-jobs-") or hit["_index"].startswith("cmssdt-jenkins-jobs-"):
      try:print("Running:",hit["_source"]['job_name'],hit["_source"]['build_number'],hit["_index"],hit['_id'])
      except Exception as e: print("Error:", e)
      running_builds_elastic[hit['_id']]=hit
for build in running_builds_elastic:
  if build not in all_local:
    hit = running_builds_elastic[build]
    hit["_source"]["job_status"]="Failed"
    resend_payload(hit)
    print("job status marked as Failed")

