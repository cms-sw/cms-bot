#!/usr/bin/python
from hashlib import sha1
import os , re , sys , json
import xml.etree.ElementTree as ET
from es_utils import send_payload,get_payload,resent_payload

def findParametersAction(root):
  if root.tag=='parameters': return root
  for x in root:
    p=findParametersAction(x)
    if p is not None: return p
  return None

def getParameters(root, payload):
  n=root.find('name')
  if n is not None:
    v=root.find('value')
    vv = "None"
    if v is not None: vv = str(v.text)
    payload['parameter_'+n.text]=vv
  else:
    for x in root: getParameters(x, payload)

query_url='http://cmses-master02.cern.ch:9200/jenkins-*/_search'
query_running_builds = """ {
  "query": {
    "filtered": {
      "query": {
        "bool": {
          "should": [
            {
              "query_string": {
                "query": "job_status:Running",
                "lowercase_expanded_terms": false
              }
            }
          ]
        }
      },
      "filter": {
        "bool": {
          "must": [
            {
              "match_all": {}
            }
          ]
        }
      }
    }
  },
  "highlight": {
    "fields": {},
    "fragment_size": 2147483647,
    "pre_tags": [
      "@start-highlight@"
    ],
    "post_tags": [
      "@end-highlight@"
    ]
  },
  "size": 500,
  "sort": [
    {
      "_score": {
        "order": "desc",
        "ignore_unmapped": true
      }
    }
  ]
} """
all_local = list() 
path = '/build/jobs'
document = "builds-data"
rematch = re.compile(".*/builds/\d+$")
for root, dirs, files in os.walk(path):
  if rematch.match(root):
    logFile = root + '/build.xml'
    flagFile = root + '/check.done'
    if os.path.exists(logFile) and not os.path.exists(flagFile):
      payload = {}
      job_info = root.split('/')
      payload['job_name'] = job_info[3]
      payload['build_number'] = job_info[-1]
      payload['url'] = "https://cmssdt.cern.ch/jenkins/job/" + job_info[3] + "/" + job_info[-1] + "/"
      id = sha1(root).hexdigest()
      try:
        tree = ET.parse(logFile)
        root = tree.getroot()
        pa=findParametersAction(root)
        if pa is not None: getParameters(pa, payload)
        jstime = root.find('startTime').text
        payload['@timestamp'] = jstime
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
        send_payload(weekindex,document,id,json.dumps(payload), passwd_file="/var/lib/jenkins/secrets/github_hook_secret_cmsbot")
      except Exception as e:
        print "Xml parsing error" , e
running_builds_elastic={}
content = get_payload(query_url,query_running_builds)
if content == "":
  running_builds_elastic = []
else:
  content_hash = json.loads(content)
  for hit in content_hash['hits']['hits']:
    if hit["_index"]=="jenkins" or hit["_index"].startswith("jenkins-jobs-"):
      running_builds_elastic[hit['_id']]=hit
for build in running_builds_elastic:
  if build not in all_local:
    hit = running_builds_elastic[build]
    hit["job_status"]="Failed"
    resent_payload(hit,passwd_file="/var/lib/jenkins/secrets/github_hook_secret_cmsbot")
    print "job status marked as Failed"

