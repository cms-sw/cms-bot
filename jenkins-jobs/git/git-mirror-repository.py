#!/usr/bin/env python3
from __future__ import print_function
from os.path import abspath, dirname
from sys import argv, exit, path
from os import environ

path.append(dirname(dirname(dirname(abspath(__file__)))))  # in order to import top level modules
from _py2with3compatibility import run_cmd, Request, urlopen, quote_plus

repo = argv[1]
e, o = run_cmd(
    'git ls-remote -h "https://:@gitlab.cern.ch:8443/%s" 2>&1 | grep "refs/heads/" | wc -l' % repo
)
if o == "0":
    print("Mirror repository not found:", repo)
    exit(0)

TOKEN_FILE = "/data/secrets/cmsbuild-gitlab-secret"
if "GITLAB_SECRET_TOKEN" in environ:
    TOKEN_FILE = environ["GITLAB_SECRET_TOKEN"]
url = "https://gitlab.cern.ch/api/v4/projects/%s/mirror/pull" % quote_plus(repo)
headers = {"PRIVATE-TOKEN": open(TOKEN_FILE).read().strip()}
request = Request(url, headers=headers)
request.get_method = lambda: "POST"
response = urlopen(request)
print(response.read())
