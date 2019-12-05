#!/usr/bin/env python
from __future__ import print_function
from os import environ
from os.path import dirname,basename,abspath
from json import dumps, dump
from optparse import OptionParser
import sys
sys.path.append(dirname(dirname(abspath(__file__)))) 
from github_utils import get_merge_prs

parser = OptionParser( usage="%prog <issue-id>" )
parser.add_option( "-s", "--start-tag", dest="start_tag" , action="store" , help="Starting tag, default is CMSSW_VERSION environment.", default=None)
parser.add_option( "-e", "--end-tag", dest="end_tag" , action="store" , help="Ending tag, default is HEAD.", default='HEAD')
parser.add_option( "-g", "--git-directory", dest="git_dir" , action="store" , help=".git directory, default is CMSSW_BASE/src/.git", default=None)
parser.add_option( "-c", "--cache-directory", dest="cache_dir" , action="store" , help="Path to cms-prs cache directory", default=None)
parser.add_option( "-o", "--out-file", dest="out_file" , action="store" , help="Outpu json file name", default=None)
opts, args = parser.parse_args( )
if len( args ) != 0:
  parser.print_help()
  parser.error( "Too many arguments" )
if not opts.start_tag:
  opts.start_tag = environ['CMSSW_VERSION']
if not opts.git_dir:
  opts.git_dir = environ['CMSSW_BASE']+"/src/.git"
if not opts.cache_dir:
  parser.error( "Please pass -c|--cache-directory /path/to/cms-prs/cms-sw/<repository>" )

repo = basename(opts.cache_dir)
opts.cache_dir = dirname(dirname(opts.cache_dir))
prs = get_merge_prs(opts.start_tag, opts.end_tag, opts.git_dir,opts.cache_dir,{},repo)
if opts.out_file:
  with open(opts.out_file,"w") as ref:
    dump(prs, ref,sort_keys=True, indent=4, separators=(',', ': '))
else:
  print(dumps(prs,sort_keys=True, indent=4, separators=(',', ': ')))
  
