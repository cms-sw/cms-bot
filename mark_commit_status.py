#!/usr/bin/env python
from __future__ import print_function
from optparse import OptionParser
from github_utils import api_rate_limits, mark_commit_status

if __name__ == "__main__":
  parser = OptionParser(usage="%prog")
  parser.add_option("-c", "--commit",     dest="commit",       help="git commit for which set the status", type=str, default=None)
  parser.add_option("-r", "--repository", dest="repository",   help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default="cms-sw/cmssw")
  parser.add_option("-d", "--description", dest="description", help="Description of the status", type=str, default="Test running")
  parser.add_option("-C", "--context",     dest="context",     help="Status context", type=str, default="default")
  parser.add_option("-u", "--url",         dest="url",         help="Status results URL", type=str, default="")
  parser.add_option("-s", "--state",       dest="state",       help="State of the status e.g. pending, failure, error or success", type=str, default='pending')
  opts, args = parser.parse_args()

  mark_commit_status(opts.commit, opts.repository, opts.context, opts.state, opts.url, opts.description)

