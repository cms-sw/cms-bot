#!/usr/bin/env python3
from __future__ import print_function
from hashlib import sha1
import os , re , sys , json, datetime, time, functools
import xml.etree.ElementTree as ET
import subprocess
from es_utils import send_payload,get_payload,resend_payload,get_payload_wscroll

JENKINS_PREFIX="jenkins"
try:    JENKINS_PREFIX=os.environ['JENKINS_URL'].strip("/").split("/")[-1]
except: JENKINS_PREFIX="jenkins"
LOCAL_JENKINS_URL = os.environ['LOCAL_JENKINS_URL']

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

def get_current_time():
    """Returns current time in milliseconds. """
    current_time = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    current_time = round(current_time.total_seconds()*1000)
    return current_time

def display_build_info(build_id, build_payload):
   """Display id, job name, build number and waiting time for a conrete build in queue. """
   print("==> ", str(build_id) + " " + str(build_payload["job_name"]) + " #" + str(build_payload["queue_id"]))
   wait_time = build_payload["wait_time"]/1000
   print("Time in queue (minutes): ", str(wait_time/60))

def update_payload_timestamp(build_id, queue):
    """Updates timestamp for a given payload. """
    id = build_id
    payload = queue[id]
    current_time = get_current_time()
    payload['@timestamp'] = current_time
    return id, payload

def process_queue_reason(labels):
    if "already in progress" in labels:
        reason = "concurrent builds not allowed"
    elif "Waiting for next available executor on" in labels:
        node = labels.split(" on ")[1].encode('ascii', errors='ignore')
        reason = str(node) + "-busy"
    elif "is offline;" in labels:
        reason = "multiple-offline"
    elif "is offline" in labels:
        node = labels.split(" is ")[0].encode('ascii', errors='ignore')
        reason = str(node) + "-offline"
    else:
        reason = "other"
    return reason

def grep(filename, pattern, verbose=False):
    """Bash-like grep function. Set verbose=True to print the line match."""
    if not os.path.exists(filename):
        return
    with open(filename, "r") as file:
        for line in file:
            if re.search(pattern, line):
                if verbose:
                    return line
                else:
                    return True

query_running_builds = """{
"query": {"bool": {"must": {"query_string": {"query": "job_status:Running AND jenkins_server:%s", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}""" % JENKINS_PREFIX

# Query job with in_queue=1
query_inqueue1 = """{
"query": {"bool": {"must": {"query_string": {"query": "in_queue: 1 AND start_time: 0 AND jenkins_server: %s", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}""" % JENKINS_PREFIX

# Query jobs with in_queue=0
query_inqueue0 = """{
"query": {"bool": {"must": {"query_string": {"query": "in_queue: 0 AND start_time: 0", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}"""

# Get jobs in queue from elastic search
queue_index = 'cmssdt-jenkins-queue*'
try:
    elements_inqueue = get_payload_wscroll(queue_index, query_inqueue1)
except ValueError:
    elements_inqueue = dict()

es_queue = dict()
es_indexes = dict()
if elements_inqueue:
  if (not 'hits' in elements_inqueue) or (not 'hits' in elements_inqueue['hits']):
    print("ERROR: ", elements_inqueue)
  for entry in elements_inqueue['hits']['hits']:
    es_indexes[entry['_id']] = entry['_index']
    es_queue[entry['_id']] = entry['_source']

# Get jenkins queue and construct payload to be send to elastic search
que_cmd='curl -s -H "OIDC_CLAIM_CERN_UPN: cmssdt; charset=UTF-8" "' + LOCAL_JENKINS_URL + '/queue/api/json?pretty=true"'
jque_res = subprocess.run(que_cmd,shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
queue_json = json.loads(jque_res.stdout)

jenkins_queue = dict()
current_time = get_current_time()
for element in queue_json["items"]:
    payload = dict()

    job_name = element["task"]["name"]
    queue_id = int(element["id"])
    queue_time = int(element["inQueueSince"])
    labels = str(element["why"].encode('utf-8'))
    reason = process_queue_reason(labels)

    payload['jenkins_server'] = JENKINS_PREFIX
    payload["in_queue_since"] = queue_time
    payload["queue_id"] = queue_id
    payload["job_name"] = job_name
    payload["node_labels"] = reason
    payload["in_queue"] = 1
    payload["wait_time"] = current_time - queue_time
    payload["start_time"] = 0

    unique_id = JENKINS_PREFIX + ":/build/builds/" + job_name + "/" + str(queue_id) # Not a real path
    id = sha1(unique_id.encode()).hexdigest()
    jenkins_queue[id] = payload

queue_index="cmssdt-jenkins-queue-"+str(int(((current_time/86400000)+4)/7))
queue_document = "queue-data"

# Update information in elastic search
new_inqueue = [x for x in jenkins_queue.keys() if x not in es_queue.keys()]
print("[INFO] Pushing new Jenkins builds in queue ...")
for build_id in new_inqueue:
    id, payload = update_payload_timestamp(build_id, jenkins_queue)
    display_build_info(id, payload)
    send_payload(queue_index,queue_document,id,json.dumps(payload))

still_inqueue = [x for x in jenkins_queue.keys() if x in es_queue.keys()]
print("[INFO] Updating waiting time for build that are still in queue ...")
for build_id in still_inqueue:
    id, payload = update_payload_timestamp(build_id, jenkins_queue)
    payload["wait_time"] = current_time - payload["in_queue_since"]
    display_build_info(id, payload)
    send_payload(es_indexes[id],queue_document,id,json.dumps(payload))

no_inqueue = [str(y) for y in es_queue.keys() if y not in jenkins_queue.keys()]
print("[INFO] Updating builds that are no longer in queue ...")
for build_id in no_inqueue:
    id, payload = update_payload_timestamp(build_id, es_queue)
    payload['in_queue'] = 0
    print("==> Cleaning up ",es_indexes[id],"/", str(id) + " " + str(payload["job_name"]) + " #" + str(payload["queue_id"]))
    send_payload(es_indexes[id],queue_document,id,json.dumps(payload))

time.sleep(10)

# Get jobs in elastic search with in_queue=0 (jobs that already started)
queue_content_hash = get_payload_wscroll("cmssdt-jenkins-queue*", query_inqueue0)
es_queue = dict()
es_indexes = dict()
for entry in queue_content_hash['hits']['hits']:
    if not 'queue_id' in entry['_source']: continue
    queue_id = entry['_source']['queue_id']
    entry['_source']['queue_hash'] = entry['_id']
    es_indexes[queue_id] = entry['_index']
    es_queue[queue_id] = entry['_source']

print("[INFO] Checking status of running/finished builds ...")
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
      id = sha1((JENKINS_PREFIX+":"+root).encode()).hexdigest()
      try:
        tree = ET.parse(logFile)
        root = tree.getroot()
        pa=findParametersAction(root)
        if pa is not None: getParameters(pa, payload)
        jstime = root.find('startTime').text
        payload['@timestamp'] = int(jstime)
        try:
          payload['slave_node'] = root.find('builtOn').text
        except:
          payload['slave_node'] = 'unknown'
        try:
          payload['queue_id'] = root.find('queueId').text
        except:
          payload['queue_id'] = 'unknown'
        payload['jenkins_server'] = JENKINS_PREFIX
        build_result = root.find('result')
        if build_result is not None:
          payload['build_result'] = build_result.text
          payload['build_duration'] = int(int(root.find('duration').text)/1000)
          payload['job_status'] = 'Finished'
          os.system('touch "' + flagFile + '"')
        else:
          payload['job_status'] = 'Running'

        # Check if job has been in queue, and update queue waiting time
        queue_id = int(payload['queue_id'])
        if queue_id in es_queue.keys():
            queue_payload = es_queue[queue_id]
            queue_payload['start_time'] = int(jstime) # start time in millisec
            queue_payload['wait_time'] = int(jstime) - queue_payload["in_queue_since"]
            queue_payload['build_number'] = payload['build_number']

            print("==> Sending payload for ", queue_payload['queue_hash'])
            send_payload(es_indexes[queue_id], queue_document, queue_payload['queue_hash'], json.dumps(queue_payload))

        all_local.append(id)
        weekindex="jenkins-jobs-"+str(int((((int(jstime)/1000)/86400)+4)/7))
        print("==>",id,payload['job_name'],payload['build_number'],payload['job_status'])
        send_payload(weekindex,document,id,json.dumps(payload))
      except Exception as e:
        print("Xml parsing error",logFile , e)

# Check remaining elements in the queue (to catch jobs that enter the queue and finish on the same iter)
print("[INFO] Checking remaining elements in queue ...")
for entry in es_queue:
    job_path = path + "/" + es_queue[entry]["job_name"]
    if not os.path.exists(job_path):
        continue
    for dir in os.listdir(job_path):
        if dir.isdigit():
            file_path = functools.reduce(os.path.join, [job_path, dir, "build.xml"])
            queue_id = grep(file_path, str(es_queue[entry]["queue_id"]), True)
            if queue_id != None:
                queue_id.replace("<queueId>", "").replace("</queueId>", "").replace("\n", "")
                jstime = grep(file_path, str("<startTime>"), True).replace("<startTime>", "").replace("</startTime>", "").replace("\n", "")
                es_queue[entry]["start_time"] = int(jstime)
                es_queue[entry]["wait_time"] = int(jstime) - es_queue[entry]["in_queue_since"]
                print("==> Sending payload for ", es_queue[entry]['queue_hash'])
                send_payload(es_indexes[entry], queue_document, es_queue[entry]['queue_hash'], json.dumps(es_queue[entry]))

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

