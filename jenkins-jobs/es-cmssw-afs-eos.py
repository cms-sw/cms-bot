#!/usr/bin/env python3
from __future__ import print_function

import sys
from os.path import abspath, dirname

sys.path.append(dirname(dirname(abspath(__file__))))
import json
from hashlib import sha1

from _py2with3compatibility import run_cmd
from cmsutils import cmsswIB2Week
from es_utils import send_payload

err, logs = run_cmd(
    "find /data/sdt/SDT/jenkins-artifacts/cmssw-afs-eos-comparison -mindepth 1 -maxdepth 1 -name '*.json' -type f"
)
for jfile in logs.split("\n"):
    if not jfile:
        continue
    print("Processing file", jfile)
    payload = {}
    try:
        payload = json.load(open(jfile))
    except ValueError as err:
        print(err)
        run_cmd("rm -f %s" % jfile)
        continue
    week, rel_sec = cmsswIB2Week(payload["release"])
    payload["@timestamp"] = rel_sec * 1000
    id = sha1(
        ("%s-%s-%s" % (payload["release"], payload["architecture"], payload["fstype"])).encode()
    ).hexdigest()
    print(payload)
    if send_payload("cmssw-afs-eos-%s" % week, "build", id, json.dumps(payload)):
        run_cmd("rm -f %s" % jfile)
