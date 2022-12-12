import datetime
import json
from hashlib import sha1
from _py2with3compatibility import run_cmd
from es_utils import send_payload, get_payload_wscroll

def get_current_time():
    """Returns current time in milliseconds. """
    current_time = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    current_time = round(current_time.total_seconds()*1000)
    return current_time

def display_build_info(build_id, build_payload):
   """ Display id, job name, build number and waiting time for a conrete build in queue. """
   print("==> ", str(build_id) + " " + str(build_payload["job_name"]) + " #" + str(build_payload["build_number"]))
   wait_time = build_payload["wait_time"]/1000
   print("Time in queue (minutes): ", str(wait_time/60))

JENKINS_PREFIX="jenkins"
try:    JENKINS_PREFIX=os.environ['JENKINS_URL'].strip("/").split("/")[-1]
except: JENKINS_PREFIX="jenkins"

document = "queue-data"

# Get jobs in elastic search with in_queue=1
query = """{
"query": {"bool": {"must": {"query_string": {"query": "in_queue: 1 AND jenkins_server: %s", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}""" % JENKINS_PREFIX

index = 'cmssdt-jenkins-queue*'
content_hash = get_payload_wscroll(index, query)
es_queue = dict()
if content_hash:
  if (not 'hits' in content_hash) or (not 'hits' in content_hash['hits']):
    print("ERROR: ", content_hash)
  for entry in content_hash['hits']['hits']:
    es_queue[entry['_id']] = entry['_source']

# Get jenkins queue and construct payload to be send to elastic search
exit_code, queue_json = run_cmd('curl -s -H "OIDC_CLAIM_CERN_UPN: localcli; charset=UTF-8" "http://localhost:8080/jenkins/queue/api/json?pretty=true"')
queue_json = json.loads(queue_json)

jenkins_queue = dict()
for element in queue_json["items"]:
    payload = dict()

    job_name = element["task"]["name"]
    build_id = str(element["id"])
    queue_time = int(element["inQueueSince"])
    current_time = get_current_time()

    payload['jenkins_server'] = JENKINS_PREFIX
    payload["in_queue_since"] = queue_time
    payload["build_number"] = build_id
    payload["job_name"] = job_name
    payload["in_queue"] = 1
    payload["wait_time"] = current_time - queue_time

    unique_id = JENKINS_PREFIX + ":" + job_name + "#" + build_id
    id = sha1(unique_id).hexdigest()
    jenkins_queue[id] = payload

queue_index="cmssdt-jenkins-queue-"+str(int(((queue_time/86400000)+4)/7))

def update_payload(build_id, queue):
    id = build_id
    payload = queue[id]
    current_time = get_current_time()
    payload['@timestamp'] = current_time

    return id, payload

new_inqueue = [x for x in jenkins_queue.keys() if x not in es_queue.keys()]
print("Pushing new Jenkins builds in queue ...")
for build_id in new_inqueue:
    id, payload = update_payload(build_id, jenkins_queue)
    display_build_info(id, payload)
    send_payload(queue_index,document,id,json.dumps(payload))

still_inqueue = [x for x in jenkins_queue.keys() if x in es_queue.keys()]
print("Updating waiting time for build that are still in queue ...")
for build_id in still_inqueue:
    id, payload = update_payload(build_id, jenkins_queue)
    payload["wait_time"] = current_time - payload["in_queue_since"]
    display_build_info(id, payload)
    send_payload(queue_index,document,id,json.dumps(payload))

no_inqueue = [str(y) for y in es_queue.keys() if y not in jenkins_queue.keys()]
print("Updating builds that are no longer in queue ...")
for build_id in no_inqueue:
    id, payload = update_payload(build_id, es_queue)
    payload['in_queue'] = 0
    print("==> Cleaning up ", str(id) + " " + str(payload["job_name"]) + " #" + str(payload["build_number"]))
    send_payload(queue_index,document,id,json.dumps(payload))
