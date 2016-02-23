#!/usr/bin/python
from hashlib import sha1
import os , re , sys , json
import xml.etree.ElementTree as ET
from es_utils import send_payload
path = '/build/jobs'
index = "jenkins"
document = "builds-data"
rematch = re.compile(".*/build/\d+$")
for root, dirs, files in os.walk(path):
  if rematch.match(root):
    logFile = root + '/build.xml'
    flagFile = root + '/check.done'
    if os.path.exists(logFile) and not os.path.exists(flagFile):
      payload = {}
      job_info = root.split('/')
      payload['job_name'] = job_info[3]
      payload['build_number'] = job_info[-1]
      id = sha1(root).hexdigest()
      try:
        tree = ET.parse(logFile)
        root = tree.getroot()
        payload['start_time'] = root.find('startTime').text
        payload['slave_node'] = root.find('builtOn').text
        build_result = root.find('result')
        if build_result is not None:
          payload['build_result'] = build_result.text
          payload['build_duration'] = root.find('duration').text
          payload['job_status'] = 'Finished'
          os.system('touch ' + flagFile)
        else:
          payload['job_status'] = 'Running'
        send_payload(index,document,id,json.dumps(payload))
       except Exception as e:
         print "Xml parsing error" , e
