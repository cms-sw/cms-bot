#!/usr/bin/env python3
"""
This job will check if there are queued jobs for jenkins slaves with 'condor' label and how many.
Then it will kill needed amount of placeholder jobs.
"""
from __future__ import print_function
from pprint import pprint
import re, sys
from os.path import dirname, abspath, join, exists
SCRIPT_DIR = dirname(abspath(sys.argv[0]))
CMS_BOT_DIR = dirname(SCRIPT_DIR)
sys.path.insert(0,CMS_BOT_DIR)
from xml.etree import cElementTree as ET
import requests
from collections import defaultdict
from os import environ
from _py2with3compatibility import run_cmd

RX_Project = re.compile('.+\/job\/(.+)\/(\d+)\/')
RX_Queue_why = re.compile(u'^Waiting for next available executor.*\u2018(.*)\u2019')
RX_Queue_nolabel = re.compile(u'^There are no nodes with the label.*\u2018(.*)\u2019')
JENKINS_URL = environ['LOCAL_JENKINS_URL']
WORKSPACE = environ['WORKSPACE']
running_job_xml = JENKINS_URL + '/api/xml?&tree=jobs[builds[url,building]]&xpath=/hudson/job/build[building="true"]&wrapper=jobs'
job_que_json = JENKINS_URL + '/queue/api/json?tree=items[url,why]'
node_labels = {}
JENKNS_REQ_HEADER = {"OIDC_CLAIM_CERN_UPN":"cmssdt"}


def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v
                     for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v)
                        for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d

def read_auto_nodes():
  nodes_jobs = {}
  auto_nodes = join(SCRIPT_DIR, 'auto-nodes.txt')
  if exists(auto_nodes):
    for line in open(auto_nodes).readlines():
      if '=' not in line: continue
      reg, job = line.strip().split('=',1)
      nodes_jobs[re.compile(reg.strip())] = job.strip()
  return nodes_jobs

def auto_node_schedule(auto_jobs):
    count=0
    for job in auto_jobs:
        jid = auto_jobs[job]
        err, out = run_cmd("cat %s/jenkins/find-jenkins-job.groovy | %s groovy = '%s' 'JENKINS_DYNAMIC_JOB_ID=%s'" % (CMS_BOT_DIR, environ['JENKINS_CLI_CMD'],job,jid))
        if err:
             count+=1
             prop_file = "jenkins-trigger-dynamic-job-%s.txt" % count
             jpram = join(SCRIPT_DIR, 'auto-nodes', job)
             run_cmd("echo 'JENKINS_DYNAMIC_JOB_NAME=%s' > %s" % (job, prop_file))
             run_cmd("echo 'JENKINS_DYNAMIC_JOB_ID=%s' >> %s" % (jid, prop_file))
             if exists (jpram):
                 run_cmd("cat %s >> %s" % (jpram, prop_file))
        else:
            print(out)
    return

def get_nodes(label):
  if label not in node_labels:
    url = "%s/label/%s/api/json?pretty=true"  % (JENKINS_URL, label)
    r_json = requests.get(url, headers=JENKNS_REQ_HEADER)
    node_labels[label] = r_json.json()
    print("Nodes to match label ",node_labels[label]['nodes'])
  return node_labels[label]['nodes']

def main():
    auto_nodes = read_auto_nodes()
    r_xml = requests.get(running_job_xml, headers=JENKNS_REQ_HEADER)
    r_json = requests.get(job_que_json, headers=JENKNS_REQ_HEADER)
    que_to_free = 0

    # get jobs that are waiting for a specific executor
    print("Queued jobs:", job_que_json)
    pprint(r_json.json())
    print("----")
    que_job_list = r_json.json()['items']
    auto_jobs = {}
    for j in que_job_list:
        label = ""
        found = False
        m = RX_Queue_why.match(j['why'])
        if m:
          label = m.group(1).encode('utf-8')
          print("Waiting for",label)
          for node in get_nodes(label):
            if re.match('^grid[1-9][0-9]*$', node['nodeName']):
              print(" Matched ",node)
              found = True
              break
        m1 = RX_Queue_nolabel.match(j['why'])
        if not label and m1 : label = m1.group(1)
        if label:
            print("Checking label:", label)
            if found:
                que_to_free += 1
            for reg in auto_nodes:
                if reg.search(label):
                    auto_jobs[auto_nodes[reg]] = j['url']
                    break

    print("Number jobs needed to free")
    pprint(que_to_free)
    print("----\n")
    print("Auto Jobs")
    pprint(auto_jobs)
    if auto_jobs:
        auto_node_schedule(auto_jobs)

    # get running placeholder job
    xml = ET.XML(r_xml.text)
    parsed_dict = etree_to_dict(xml)
    print("Running jobs", running_job_xml )
    pprint(parsed_dict)
    jobs_to_kill = []
    if not isinstance(parsed_dict['jobs']['build'],list):
        parsed_dict['jobs']['build']=[parsed_dict['jobs']['build']]
    for el in parsed_dict['jobs']['build']:
        match = RX_Project.match(el['url'])
        project = match.group(1)
        j_number = match.group(2)
        if 'grid-keep-node-busy' != project:
            continue
        jobs_to_kill.append([project, j_number])
    print("Jobs to kill:")
    pprint(jobs_to_kill)
    print("size:" + str(len(jobs_to_kill)))

    # create property file for each job to be killed
    for i in range(0, min(que_to_free, len(jobs_to_kill))):
        with open("{0}/job-to-kill-{1}.txt".format(WORKSPACE, i), 'w') as f:
            f.write("JENKINS_PROJECT_TO_KILL={0}\nBUILD_NR={1}\n".format(*jobs_to_kill[i]))


if __name__ == '__main__':
    main()
