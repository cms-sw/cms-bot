#!/usr/bin/env python3
from __future__ import print_function
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from releases import *
from categories import *
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import re
# Validate the schema of watchers.

KEY_RE = "^[^@]+"
VALUE_RE = "[A-Za-z0-0.*+]"

w = yaml.load(open("watchers.yaml", "r"), Loader=Loader)
assert(type(w) == dict)
for (key, value) in w.items():
  assert(type(key) == str)
  assert(re.match(KEY_RE, key))
  assert(type(value) == list)
  for x in value:
    assert(type(x) == str)
    assert(re.match(VALUE_RE, x))


assert(CMSSW_CATEGORIES)
assert(type(CMSSW_CATEGORIES) == dict)

PACKAGE_RE = "^([A-Z][0-9A-Za-z]*(/[a-zA-Z][0-9A-Za-z]*|)|.gitignore|pull_request_template.md|.clang-[^/]+)$"

for (key, value) in CMSSW_CATEGORIES.items():
  assert(type(key) == str)
  assert(type(value) == list)
  if len(value)==0:continue
  if key == "externals":
    assert(len(value)>0)
    continue
  for p in value:
    print("checking", p)
    assert(type(p) == str)
    assert(re.match(PACKAGE_RE, p))

if os.path.exists("super-users.yaml"):
  w = yaml.load(open("super-users.yaml", "r"), Loader=Loader)
  assert(type(w) == list)
  for p in w:
    assert(type(p) == str)
    assert(re.match(KEY_RE, p))

print("Finished with success")
