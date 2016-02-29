#!/usr/bin/python
from hashlib import sha1
import os , re , sys , json
import xml.etree.ElementTree as ET
from es_utils import send_payload
from es_utils import get_payload
query_url='http://cmses-master01.cern.ch:9200/jenkins/_search'
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
index = "jenkins"
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
        payload['@timestamp'] = root.find('startTime').text
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
        send_payload(index,document,id,json.dumps(payload))
      except Exception as e:
        print "Xml parsing error" , e
running_builds_elastic=list()
content = get_payload(query_url,query_running_builds)
if content == "":
  running_builds_elastic = []
else:
  content_hash = json.loads(content)
  last=int(len(content_hash["hits"]["hits"]))
  for i in range(0,last):
    running_builds_elastic.append(str(content_hash["hits"]["hits"][i]["_id"]))
for build in running_builds_elastic:
  if build not in all_local:
    send_payload(index,document,build,'{"job_status":"Failed"}')
    print "job status marked as Failed"

