#!/usr/bin/env python3

import argparse
from es_utils import get_payload_wscroll
from datetime import datetime


parser = argparse.ArgumentParser()

parser.add_argument('release', type=str, help='CMSSW Release')
parser.add_argument('arch', type=str, help='Architecture <os_arch_gccX>')
parser.add_argument('file_path', type=str, help='Output file')
args = parser.parse_args()

cmssw_release = args.release
architecture = args.arch
out_file = args.file_path

month = datetime.now().month
if month < 10: month = str(0) + str(month)
day = datetime.now().day
if day < 10: day = str(0) + str(day)
year = datetime.now().year
 
release = cmssw_release + "_" + str(year) + "-" + str(month) + "-" + str(day-2)

print("Searching relval failures for ", release) 

JENKINS_PREFIX="jenkins"
try:    JENKINS_PREFIX=os.environ['JENKINS_URL'].strip("/").split("/")[-1]
except: JENKINS_PREFIX="jenkins"

query_relval_failures = """{
"query": {"bool": {"must": {"query_string": {"query": "release:%s-2300 AND architecture:%s AND NOT exit_code:0", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}""" % (release, architecture)

content_hash = get_payload_wscroll('cmssdt-ib-matrix-*', query_relval_failures)

if content_hash:
  if (not 'hits' in content_hash) or (not 'hits' in content_hash['hits']):
    print("ERROR: ", content)
    sys.exit(1)

  with open(out_file, "w") as results_file:
    for hit in content_hash['hits']['hits']:
      relval = hit["_source"]["workflow"]
      step = hit["_source"]["step"]
      results_file.write(f"RelVal wf {relval} failed in {step} \n")
