#!/usr/bin/env python
from optparse import OptionParser
import json

parser = OptionParser(usage="%prog -q <query> -c <cache>")
parser.add_option("-q", "--query", dest="query",   default=None,    help="DAS query string.")
parser.add_option("-c", "--cache", dest="cache",   default=None,    help="DAS cache query file.")

opts, args = parser.parse_args()
if len(args)>0:parser.error("Too many arguments")
if not opts.cache: parser.error("Missing das cache command-line argument.")
if not opts.query: parser.error("Missing das query command-line argument.")

das_cache = json.loads(open(opts.cache).read())
das_results=[]
if opts.query in das_cache:
  das_results=das_cache[opts.query]

print "\n".join(das_results)

