#!/usr/bin/env python
from operator import itemgetter
from time import sleep, time
from es_utils import es_query_new, format, es_workflow_stats
from optparse import OptionParser
parser = OptionParser(usage="%prog [-m|--memory <memory>] [-c|--cpu <cpu>] [-j|--jobs <jobs-json-file>]")
parser.add_option("-i", "--index",  dest="index",  default=None, help="Name of the ElasticSearch Index e.g. ib-matrix-*")
parser.add_option("-q", "--query",  dest="query",  default=None, help="Query string e.g. release:RELEASE AND architecture:ARCH")
parser.add_option("-d", "--days",   dest="days",   default=7, type="int", help="Number of days to search data for, default is 7")
parser.add_option("-o", "--offset", dest="offset", default=0, type="int", help="Number of days to offset from the current day. Default is 0")
opts, args = parser.parse_args()

end_time=(int(time())-(opts.offset*86400))*1000
start_time = end_time-(86400*1000*opts.days)
stats = es_query_new(index=opts.index,query=opts.query,start_time=start_time,end_time=end_time)
print json.dumps(es_data, indent=2, sort_keys=True, separators=(',',': '))
