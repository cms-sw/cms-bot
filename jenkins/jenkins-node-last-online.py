#!/usr/bin/env python3

import argparse
import datetime
import json
import os.path
import sys
import time
import urllib
from hashlib import sha1

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import es_utils


JENKINS_PREFIX = "jenkins"
try:
    JENKINS_PREFIX = os.environ["JENKINS_URL"].strip("/").split("/")[-1]
except:
    JENKINS_PREFIX = "jenkins"


def sha1hexdigest(data):
    return sha1(data.encode()).hexdigest()


def main(dryrun):
    req = urllib.request.Request(
        "http://localhost:8080/jenkins/manage/computer/api/json?tree=computer[displayName,monitorData[*]]"
    )
    req.add_header("OIDC_CLAIM_CERN_UPN", "cmsbuild")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())

    for comp in data["computer"]:
        responseTime = None

        try:
            responseTimeMonitor = comp["monitorData"]["hudson.node_monitors.ResponseTimeMonitor"]
            if responseTimeMonitor is not None:
                responseTime = responseTimeMonitor["timestamp"]
        except KeyError:
            print("Could not get timestamp for node ", comp.get("displayName", "?"))

        if responseTime is None:
            continue

        document_id = sha1hexdigest(comp["displayName"])
        if not dryrun:
            es_utils.send_payload(
                "cmssdt-jenkins-node",
                "node",
                document_id,
                json.dumps(
                    {
                        "jenkins_server": JENKINS_PREFIX,
                        "node_name": comp["displayName"],
                        "timestamp": responseTime,
                    }
                ),
            )
        else:
            print(
                "Send payload for document",
                document_id,
                json.dumps(
                    {
                        "jenkins_server": JENKINS_PREFIX,
                        "node_name": comp["displayName"],
                        "timestamp": responseTime,
                    }
                ),
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--dry-run", action="store_true", dest="dryrun")
    args = parser.parse_args()

    # Set start time
    start_time = datetime.datetime.now()
    while True:
        current_time = datetime.datetime.now()
        elapsed_time = current_time - start_time
        if elapsed_time > datetime.timedelta(hours=2):
            break

        main(args.dryrun)
        time.sleep(2)
