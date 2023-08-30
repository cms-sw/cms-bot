#!/usr/bin/env python3
from optparse import OptionParser
from jenkins_callback import build_jobs
import json

def process(opts):
  xparam = []
  for param in opts.params:
    p,v=param.split("=",1)
    xparam.append({"name":p,"value":v})
  build_jobs(opts.server, [(json.dumps({"parameter":xparam}),opts.job)], headers={}, user=opts.user)

if __name__ == "__main__":
  parser = OptionParser(usage="%prog")
  parser.add_option("-j", "--job",        dest="job",        help="Jenkins jobs to trigger", default=None)
  parser.add_option("-s", "--server",     dest="server",     help="Jenkins server URL e.g. https://cmssdt.cern.ch/cms-jenkins", default=None)
  parser.add_option("-u", "--user",       dest="user",       help="Jenkins user name to trigger the job", default="cmssdt")
  parser.add_option('-p', '--parameter',  dest='params',     help="Job parameter e.g. -p Param=Value. One can use this multiple times.",
                    action="append", type="string", metavar="PARAMETERS")
  opts, args = parser.parse_args()

  if (not opts.job) or (not opts.server): parser.error("Missing job/server parameter.")
  process(opts)
