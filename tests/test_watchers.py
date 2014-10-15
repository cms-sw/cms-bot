#!/usr/bin/env python

from releases import *
from categories import *
import yaml
import re
# Validate the schema of watchers.

KEY_RE = "[^@]+"
VALUE_RE = "[A-Za-z0-0.*+]"

w = yaml.load(open("watchers.yaml", "r"))
assert(type(w) == dict)
for (key, value) in w.items():
  assert(type(key) == str)
  assert(re.match(KEY_RE, key))
  assert(type(value) == list)
  for x in value:
    assert(type(x) == str)
    assert(re.match(VALUE_RE, x))
