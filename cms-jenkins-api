#!/usr/bin/env python
# A script to communicate with jenkins in a secure way.
from __future__ import print_function
import json
import sys
import os
from _py2with3compatibility import run_cmd
from argparse import ArgumentParser

COOKIE_JAR="~/private/ssocookie.txt"
JENKINS_URL="https://cmssdt.cern.ch/jenkins"
TOKEN_CMD="cern-get-sso-cookie --krb -u %(url)s -o %(jar)s"
API_CMD="curl -k -L --cookie %(jar)s --cookie-jar %(jar)s -X POST %(url)s/%(api)s --data-urlencode json='%(json)s' --user cmsbuild:%(token)s"

def format(s, **kwds):
  return s % kwds

if __name__ == "__main__":
  parser = ArgumentParser()
  parser.add_argument("api", nargs=1, help="The api call to make.")
  parser.add_argument("--url", dest="url", default=JENKINS_URL, help="The jenkins server.")
  parser.add_argument("--cookie-jar", dest="jar", default=COOKIE_JAR, help="Where to find the cookie jar.")
  parser.add_argument("args", nargs="*", help="Key value pair arguments")
  args = parser.parse_args()
  err, out = run_cmd(format(TOKEN_CMD, url=JENKINS_URL, jar=COOKIE_JAR))
  if err:
    parser.error("Unable to get token")
  
  print(args.api[0])
  json = json.dumps({"parameter": [dict(list(zip(["name", "value"], x.split("=")))) for x in args.args]})
  print(json)
  cmd = format(API_CMD, url=args.url, jar=args.jar, api=args.api[0], json=json, token=os.getenv("HUBOT_JENKINS_TOKEN"))
  print(cmd)
  err, out = run_cmd(cmd)
  if err:
    print(out)
    sys.exit(1)
  print(out)
  sys.exit(0)
