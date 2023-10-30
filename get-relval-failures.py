#!/usr/bin/env python3
import argparse
from es_utils import get_payload_wscroll

parser = argparse.ArgumentParser()
parser.add_argument("release", type=str, help="CMSSW Release")
parser.add_argument("arch", type=str, help="Architecture <os_arch_gccX>")
args = parser.parse_args()

print("Searching relval failures for %s/%s" % (args.release, args.arch))

query_relval_failures = """{
"query": {"bool": {"must": {"query_string": {"query": "release:%s AND architecture:%s AND NOT exitcode:0", "default_operator": "AND"}}}},
"from": 0,
"size": 10000
}""" % (
    args.release,
    args.arch,
)

content_hash = get_payload_wscroll("cmssdt-ib-matrix-*", query_relval_failures)

if content_hash:
    if (not "hits" in content_hash) or (not "hits" in content_hash["hits"]):
        print("ERROR: ", content_hash)
        sys.exit(1)

    for hit in content_hash["hits"]["hits"]:
        relval = hit["_source"]["workflow"]
        step = hit["_source"]["step"]
        exitcode = hit["_source"]["exitcode"]
        print(f"WF:{relval}:{step}:{exitcode}")
