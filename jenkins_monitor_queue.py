#!/usr/bin/env python3

import datetime, json
import sys
import os
from hashlib import sha1
from es_utils import get_payload_wscroll, send_payload, delete_hit

JENKINS_PREFIX="jenkins"
try:    JENKINS_PREFIX=os.environ['JENKINS_URL'].strip("/").split("/")[-1]
except: JENKINS_PREFIX="jenkins"

query_pending_builds = """{
"query": {"bool": {"must": {"query_string": {"query": "_index:cmssdt-jenkins-queue-* AND in_queue:1 AND jenkins_server:%s", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}""" % JENKINS_PREFIX

query_offline_nodes = """{
"query": {"bool": {"must": {"query_string": {"query": "jenkins_server:%s", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}""" % JENKINS_PREFIX


queue_index="cmssdt-jenkins-offline-nodes"
queue_document = "offline-data"

max_time = 60
current_offline_nodes = []

content_hash = get_payload_wscroll('cmssdt-jenkins-queue-*', query_pending_builds)
if content_hash:
  if (not 'hits' in content_hash) or (not 'hits' in content_hash['hits']):
    print("ERROR: ", content_hash)
    sys.exit(1)

  print("Found " + str(len(content_hash['hits']['hits'])) + " jobs in queue!")
  for hit in content_hash['hits']['hits']:
    job_name = hit["_source"]["job_name"]
    queue_time = int(hit["_source"]["wait_time"])/(60*1000)
    print("[" + str(hit["_source"]["node_labels"])  + "] Job " + str(job_name) + " has been in queue " + str(queue_time) + " minutes..." )

    payload = {}
    if "offline" in hit["_source"]["node_labels"]:
      offline_time = int(hit["_source"]["wait_time"])/(60*1000)
      print("--> Found job in queue due to an offline node: ", hit["_source"])
      print("Offline minutes: ", offline_time)
      if int(offline_time) > int(max_time):
          node = hit["_source"]["node_labels"].split("-offline")[0]
          current_offline_nodes.append(node)
          print("[WARNING] Node " + str(node) + " has been offline for more than " + str(max_time) + " minutes!")
          payload['jenkins_server'] = JENKINS_PREFIX
          payload["node_name"] = node
          payload["offline_time"] = offline_time

          # Update data on the same id for each node
          unique_id = JENKINS_PREFIX + "-" + node
          id = sha1(unique_id.encode('utf-8')).hexdigest()

          # Update timestamp in milliseconds
          current_time = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
          payload['@timestamp'] = round(current_time.total_seconds()*1000)

          send_payload(queue_index,queue_document,id,json.dumps(payload))

content_hash = get_payload_wscroll('cmssdt-jenkins-offline-node*', query_offline_nodes)

es_offline_nodes = []
if content_hash:
  if (not 'hits' in content_hash) or (not 'hits' in content_hash['hits']):
    print("ERROR: ", content_hash)
    sys.exit(1)

  print("Found " + str(len(content_hash['hits']['hits'])) + " nodes already online!")
  for hit in content_hash['hits']['hits']:
     es_offline_nodes.append(str(hit["_source"]["node_name"]))

for node in es_offline_nodes:
  if node not in current_offline_nodes:
    unique_id = JENKINS_PREFIX + "-" + node
    id = sha1(unique_id.encode('utf-8')).hexdigest()
    hit = {"_index": "cmssdt-jenkins-offline-nodes", "_id": id}

    print("--> Deleting entry for node " + str(node) + ":" + str(hit) )
    delete_hit(hit)
