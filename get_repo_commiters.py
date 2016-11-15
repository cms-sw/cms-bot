#!/bin/env python
from os.path import basename
from sys import argv, exit
from commands import getstatusoutput as run
from json import loads, dumps
try:
  commiters_info = {}
  repo = argv[1]
  err, output = run("curl -s https://api.github.com/repos/" + repo + "/stats/contributors")
  if err: exit(1)
  data = loads(output)
  if not data: exit(1)
  for item in data:
    commiters_info[item['author']['login']] = item['total']  
  print basename(repo).upper().replace('-','_') + "_COMMITER=",dumps(commiters_info,sort_keys=True, indent=4)
except IndexError:
  print "Repo Name Required ... Arugement missing !!!!"
  exit (1)

