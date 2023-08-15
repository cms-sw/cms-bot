#!/usr/bin/env python3
from __future__ import print_function
from sys import argv
from os.path import join, exists
exceptions_regexp = []

uniq_paths = []
for file_path in [ f.strip("\n").strip("/") for f in open(argv[1]).readlines()]:
  if not file_path or [ r for r in exceptions_regexp if r.match(file_path) ] : continue
  xpath = ""
  for sub_path in file_path.split('/'):
    xpath=join(xpath,sub_path)
    if not sub_path[:1].isdigit(): continue
    #If it exists then we allow to have files with [0-9] under it
    if exists(join(argv[2],xpath)): break
    if not xpath in uniq_paths: uniq_paths.append(xpath)
    break
if uniq_paths:
  print("\n".join(uniq_paths))
