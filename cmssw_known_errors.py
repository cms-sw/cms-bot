#!/usr/bin/env python

KNOWN_ERRORS = {"relvals":{}, "addons":{}, "unittests":{}}
KNOWN_ERRORS["relvals"]["CMSSW_9_2_X"]={
  "slc6_amd64_gcc630": {
    "512.0": { "step": "step1", "exitcode": 16640},
    "513.0": { "step": "step1", "exitcode": 16640},
    "515.0": { "step": "step1", "exitcode": 16640},
    "516.0": { "step": "step1", "exitcode": 16640},
    "518.0": { "step": "step1", "exitcode": 16640},
    "519.0": { "step": "step1", "exitcode": 16640},
    "521.0": { "step": "step1", "exitcode": 16640},
    "525.0": { "step": "step1", "exitcode": 16640},
    "526.0": { "step": "step1", "exitcode": 16640},
    "528.0": { "step": "step1", "exitcode": 16640},
    "529.0": { "step": "step1", "exitcode": 16640},
    "534.0": { "step": "step1", "exitcode": 16640}
  },
  "slc7_aarch64_gcc700": {
    "512.0": { "step": "step1", "exitcode": 16640},
    "513.0": { "step": "step1", "exitcode": 16640},
    "515.0": { "step": "step1", "exitcode": 16640},
    "516.0": { "step": "step1", "exitcode": 16640},
    "518.0": { "step": "step1", "exitcode": 16640},
    "519.0": { "step": "step1", "exitcode": 16640},
    "521.0": { "step": "step1", "exitcode": 16640},
    "525.0": { "step": "step1", "exitcode": 16640},
    "526.0": { "step": "step1", "exitcode": 16640},
    "528.0": { "step": "step1", "exitcode": 16640},
    "529.0": { "step": "step1", "exitcode": 16640},
    "534.0": { "step": "step1", "exitcode": 16640}
  },
  "slc7_aarch64_gcc530": {
    "512.0": { "step": "step1", "exitcode": 16640},
    "513.0": { "step": "step1", "exitcode": 16640},
    "515.0": { "step": "step1", "exitcode": 16640},
    "516.0": { "step": "step1", "exitcode": 16640},
    "518.0": { "step": "step1", "exitcode": 16640},
    "519.0": { "step": "step1", "exitcode": 16640},
    "521.0": { "step": "step1", "exitcode": 16640},
    "525.0": { "step": "step1", "exitcode": 16640},
    "526.0": { "step": "step1", "exitcode": 16640},
    "528.0": { "step": "step1", "exitcode": 16640},
    "529.0": { "step": "step1", "exitcode": 16640},
    "534.0": { "step": "step1", "exitcode": 16640}
  }
}

if __name__ == "__main__":
  from json import dumps
  print dumps(KNOWN_ERRORS,sort_keys=True,indent=2)

