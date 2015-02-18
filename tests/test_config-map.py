#!/usr/bin/env python

import re

KEYS_RE="(SCRAM_ARCH|RELEASE_QUEUE|PKGTOOLS_TAG|CMSDIST_TAG|RELEASE_BRANCH|ADDITIONAL_TESTS|PR_TESTS|DISABLED|ALWAYS_TAG_CMSSW|DO_STATIC_CHECKS|PROD_ARCH|ENABLE_DEBUG|PRS_TEST_CLANG)"

if __name__ == "__main__":
  for l in open("config.map").read().split("\n"):
    if not l:
      continue
    l = l.strip(";")
    for p in l.split(";"):
      assert("=" in p)
      (key, value) = p.split("=")
      assert(re.match(KEYS_RE, key))
