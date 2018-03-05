import json, sys
from time import time
from es_utils import get_payload
from ROOT import *

'''
this program uses pyROOT, no brainer would be to set cmsenv before running it
'''

def _format(s, **kwds):
    return s % kwds

def getWorkflowStatsFromES(release='*', arch='*', lastNdays=7, page_size=0):

    query_url = 'http://cmses-master02.cern.ch:9200/relvals_stats_*/_search'

    query_datsets = """
        {
          "query": {
            "filtered": {
              "query": {
                "bool": {
                  "should": [
                    {
                      "query_string": {
                        "query": "release:%(release_cycle)s AND architecture:%(architecture)s", 
                        "lowercase_expanded_terms": false
                      }
                    }
                  ]
                }
              },
              "filter": {
                "bool": {
                  "must": [
                    {
                      "range": {
                        "@timestamp": {
                          "from": %(start_time)s,
                          "to": %(end_time)s
                        }
                      }
                    }
                  ]
                }
              }
            }
          },
          "from": %(from)s,
          "size": %(page_size)s
        }
        """
    datasets = {}
    ent_from = 0
    json_out = []
    info_request = False
    queryInfo = {}

    queryInfo["end_time"] = int(time() * 1000)
    queryInfo["start_time"] = queryInfo["end_time"] - int(86400 * 1000 * lastNdays)
    queryInfo["architecture"] = arch
    queryInfo["release_cycle"] = release
    queryInfo["from"] = 0

    if page_size < 1:
        info_request = True
        queryInfo["page_size"] = 2
    else:
        queryInfo["page_size"] = page_size

    total_hits = 0

    while True:
        queryInfo["from"] = ent_from
        es_data = get_payload(query_url, _format(query_datsets, **queryInfo))  # here
        content = json.loads(es_data)
        content.pop("_shards", None)
        total_hits = content['hits']['total']
        if info_request:
            info_request = False
            queryInfo["page_size"] = total_hits
            continue
        hits = len(content['hits']['hits'])
        if hits == 0: break
        ent_from = ent_from + hits
        json_out.append(content)
        if ent_from >= total_hits:
            break

    return json_out[0]['hits']['hits']

'''
have a function that narrows the result to fields of interest, described in a list and in the given order
'''

def filterElasticSearchResult(ES_result=None, list_of_fields=None):

    #arch = ES_result[0]['_source']['architecture']
    #print arch
    final_struct = {}

    for element in ES_result:

        source_object = element['_source']

        stamp = source_object['@timestamp']
        flow = source_object['workflow']
        step = source_object['step']

        if not stamp in final_struct:
            final_struct.update({stamp: {}})
        if not flow in final_struct[stamp]:
            final_struct[stamp].update({flow: {}})

        step_data = {}
        for stat_item in list_of_fields:
            step_data.update({stat_item: source_object[stat_item]})

        final_struct[stamp][flow].update({step: step_data})

    return final_struct

'''
deeper in this context :)  ,this function 
1. gets two objects filtered after the ES query
2. for each sub-step key found tries to find the same in both objects and to make the difference between their values
'''

def compareMetrics(firstObject=None, secondObject=None):

    fields = []
    comparison_results = {}

    for stamp in firstObject:
        for wf in firstObject[stamp]:
            for step in firstObject[stamp][wf]:
                fields =  firstObject[stamp][wf][step].keys()
                break
            break
        break

    for f in fields:
        comparison_results.update({f: []})

    for stamp in firstObject:
        for wf in firstObject[stamp]:
            for step in firstObject[stamp][wf]:
                for field in firstObject[stamp][wf][step]:
                    #print field
                    if stamp in secondObject and wf in secondObject[stamp] \
                            and step in secondObject[stamp][wf] \
                            and field in secondObject[stamp][wf][step]:
                        first_metric = firstObject[stamp][wf][step][field]
                        second_metric = secondObject[stamp][wf][step][field]
                        if field is 'time' or 'cpu_avg':
                            difference = first_metric - second_metric
                        if field is 'rss_avg':
                            difference = float( float(first_metric) / float(second_metric) ) * 100
                        
                        comparison_results[field].append(difference)

    return comparison_results

if __name__ == "__main__":

    opts = None
    release = None
    fields = ['time', 'rss_avg', 'cpu_avg']

    arch = 'slc6_amd64_gcc630'
    days = 7
    page_size = 0
    limit = 20

    #release_one = 'CMSSW_10_1_X_2018-*'
    #release_two = 'CMSSW_10_1_ROOT612_X_2018-*'
    release_one = sys.argv[1]
    release_two = sys.argv[2]

    json_out_first = getWorkflowStatsFromES(release_one, arch, days, page_size)
    json_out_second = getWorkflowStatsFromES(release_two, arch, days, page_size)

    filtered_first = filterElasticSearchResult(json_out_first,fields)
    filtered_second = filterElasticSearchResult(json_out_second,fields)

    comp_results = compareMetrics(filtered_first, filtered_second)
    print json.dumps(comp_results, indent=2, sort_keys=True, separators=(',', ': '))
    
    c1 = TCanvas( 'c1', '', 200, 10, 700, 500 )

    for hist in comp_results:
        histo = TH1F(hist, hist, 10000, -500, 500)
        for i in comp_results[hist]:
            histo.Fill(i)
        histo.SaveAs(hist+".root")
