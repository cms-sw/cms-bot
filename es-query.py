#!/usr/bin/env python
from operator import itemgetter
from time import sleep, time
from es_utils import es_query, format, es_workflow_stats
from optparse import OptionParser
parser = OptionParser(usage="%prog [-m|--memory <memory>] [-c|--cpu <cpu>] [-j|--jobs <jobs-json-file>]")
parser.add_option("-i", "--index",  dest="index",  default=None, help="Name of the ElasticSearch Index e.g. ib-matrix-*")
parser.add_option("-q", "--query",  dest="query",  default=None, help="Query string e.g. release:RELEASE AND architecture:ARCH")
parser.add_option("-d", "--days",   dest="days",   default=7, type="int", help="Number of days to search data for, default is 7")
parser.add_option("-o", "--offset", dest="offset", default=0, type="int", help="Number of days to offset from the current day. Default is 0")
opts, args = parser.parse_args()

end_time=int(time())-(opts.offset*86400)
stats = es_query(index=opts.index,query=opts.query,start_time=1000*(end_time-(86400*opts.days)),end_time=end_time*1000)
matched=[]
for h in stats['hits']['hits']:
  hit = h["_source"]
  if 'TBranchElement::GetBasket' in hit['exception']: matched.append(hit)

for hit in sorted(matched,key=itemgetter('@timestamp')):
    print "Release:",hit['release'],"\nArchitecture:",hit['architecture'],"\nWorkflow:",hit['workflow']+"/"+hit['step'],"\nException:",hit['exception'],"\n-----------------------------------------"

