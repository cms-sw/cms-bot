#!/usr/bin/env python
from copy import deepcopy

MSG_GCC_ABI_INCOMPETIBILITY = "GCC ABI incompetibility. GridPacks were built with gcc4"
MSG_ARCH_INCOMPETIBILITY = "Architecture incompetibility. GridPacks were built for x86_64"
KNOWN_ERRORS = {"relvals":{}, "addons":{}, "unittests":{}}
KNOWN_ERRORS["relvals"]["CMSSW_9_[2-9]_.+"]={
  "slc._amd64_gcc630": {
    "512.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "513.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "515.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "516.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "518.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "519.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "521.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "522.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "525.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "526.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "528.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "529.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
    "534.0": { "step": 1, "exitcode": 35584, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  }
}
KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"]={}
KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"]["slc7_amd64_gcc630"]=deepcopy(KNOWN_ERRORS["relvals"]["CMSSW_9_[2-9]_.+"]["slc._amd64_gcc630"])
KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"][".+_amd64_gcc700"]={
  "512.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "513.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "514.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "515.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "516.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "517.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "518.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "519.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "520.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "521.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "522.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "523.0": { "step": 1, "exitcode": 31744, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "524.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "525.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "526.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "527.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "528.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "529.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "530.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "534.0": { "step": 1, "exitcode": 35584, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "551.0": { "step": 1, "exitcode": 31744, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "552.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "554.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "555.0": { "step": 1, "exitcode": 31744, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "556.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "562.0": { "step": 1, "exitcode": 16640, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "1360.0": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "1361.0": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "1362.0": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "1363.0": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "1361.17": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "1362.17": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "1363.17": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "25210.0": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "25211.0": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "25212.0": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "25213.0": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "25211.17": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "25212.17": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
  "25213.17": { "step": 1, "exitcode": 34304, "reason" : MSG_GCC_ABI_INCOMPETIBILITY},
}
KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"][".+_aarch64_.+"]=deepcopy(KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"][".+_amd64_gcc700"])
for wf in KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"][".+_aarch64_.+"]:
  KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"][".+_aarch64_.+"][wf]["reason"]=MSG_ARCH_INCOMPETIBILITY
  
KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"][".+_aarch64_.+"]["534.0"]["exitcode"]=256

for xwf in ["136","2521"]:
  for wf in KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"][".+_aarch64_.+"]:
    if wf.startswith(xwf): KNOWN_ERRORS["relvals"]["CMSSW_[1-9][0-9]+_.+"][".+_aarch64_.+"][wf]["exitcode"]=64000

def get_known_errors(release, architecture, test_type):
  if not test_type in KNOWN_ERRORS: return {}
  from re import match
  errs = {}
  for rel in KNOWN_ERRORS[test_type]:
    if not match(rel,release): continue
    for arch in KNOWN_ERRORS[test_type][rel]:
      if not match(arch,architecture): continue
      for test in KNOWN_ERRORS[test_type][rel][arch]:
        obj = KNOWN_ERRORS[test_type][rel][arch][test]
        if not obj:
          if test in errs: del errs[test]
        else:
          errs[test]=obj
  return errs

if __name__ == "__main__":
  from json import dumps
  print dumps(KNOWN_ERRORS,sort_keys=True,indent=2)

