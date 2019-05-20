#!/usr/bin/env python
# This script can be used to sync the production releases which are
# declared as announced in the tag collector and 
from __future__ import print_function
from optparse import OptionParser
from _py2with3compatibility import run_cmd
from sys import exit
# Apparently there are many ways to import json, depending on the python
# version. This should make sure you get one.
from os.path import join, dirname

HOME_DIR = dirname(__file__)

def getAnnouncedReleases():
  lines = open(join(HOME_DIR, "releases.map")).readlines()
  releases = []
  for l in lines:
    l = l.strip("\n ")
    data = dict([p.split("=") for p in l.split(";") if p])
    if data["type"] != "Production":
      continue
    if data["state"] != "Announced":
      continue
    releases.append(data["label"])
  return releases

def withGridEnv(command, **kwds):
  opts = {"environment": "/afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh",
          "command": command % kwds}
  return run_cmd("source %(environment)s ; %(command)s" % opts)

def availableCes():
  error, out = withGridEnv("lcg-info --vo cms --list-ce"
                           " --query 'Cluster=*.cern.ch'"
                           " | grep -E -o '[a-zA-Z0-9.-]+[.]cern[.]ch'"
                           " | sort -u")
  if error:
    return None
  return out.split("\n")

def gridReleases(ce):
  error, out = withGridEnv("lcg-tags --vo cms --ce %(ce)s --list", ce=ce)
  if error:
    return None
  return ["CMSSW_" + x.split("CMSSW_")[1] 
          for x in out.split("\n") 
          if "CMSSW_" in x]

def announceRelease(ce, release):
  error, out = withGridEnv("lcg-tags --ce %(ce)s --vo cms --add --tags VO-cms-%(release)s",
                           ce=ce,
                           release=release) 
  return (release, error)

if __name__ == "__main__":
  parser = OptionParser(usage="%(prog)s")
  announced = getAnnouncedReleases()

  error, out = withGridEnv("voms-proxy-init -voms %(voms)s",
                            voms="cms:/cms/Role=lcgadmin")
  if error:
    parser.error("Could not get a proxy")

  ces = availableCes()
  if not ces:
    parser.error("Could not find any CE")

  grids = gridReleases(ces[0])
  missingReleases = [x for x in announced if x not in grids]
  if not missingReleases:
    print("No releases to announce")
    exit(0)

  errors = []
  for ce in ces:
    announced = [announceRelease(ce, x) for x in missingReleases]
    errors += ["Release %s cannot be announced on %s" % (x,ce)
               for (x, err) in announced if err]
    ok = ["Release %s announced." % (x,ce)
          for (x, err) in announced if err] 
    if not errors:
      print("\n".join(ok))
      break

    print("\n".join(errors))
