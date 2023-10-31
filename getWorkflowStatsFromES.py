from __future__ import print_function

import sys
from time import time
from es_utils import es_query, format

from ROOT import *

"""
this program uses pyROOT, no brainer would be to set cmsenv before running it
"""


def _format(s, **kwds):
    return s % kwds


def getWorkflowStatsFromES(release="*", arch="*", lastNdays=7, page_size=0):
    stats = es_query(
        index="relvals_stats_*",
        query=format(
            "(NOT cpu_max:0) AND (exit_code:0) AND release:%(release_cycle)s AND architecture:%(architecture)s",
            release_cycle=release + "_*",
            architecture=arch,
        ),
        start_time=1000 * int(time() - (86400 * lastNdays)),
        end_time=1000 * int(time()),
        scroll=True,
    )
    return stats["hits"]["hits"]


"""
have a function that narrows the result to fields of interest, described in a list and in the given order
"""


def filterElasticSearchResult(ES_result=None, list_of_fields=None):
    # arch = ES_result[0]['_source']['architecture']
    # print arch
    final_struct = {}

    for element in ES_result:
        source_object = element["_source"]
        if source_object["exit_code"] is not 0:
            continue

        stamp = source_object["@timestamp"]
        flow = source_object["workflow"]
        step = source_object["step"]

        if not stamp in final_struct:
            final_struct.update({stamp: {}})
        if not flow in final_struct[stamp]:
            final_struct[stamp].update({flow: {}})

        step_data = {}
        for stat_item in list_of_fields:
            step_data.update({stat_item: source_object[stat_item]})

        final_struct[stamp][flow].update({step: step_data})

    return final_struct


"""
deeper in this context :)  ,this function 
1. gets two objects filtered after the ES query
2. for each sub-step key found tries to find the same in both objects and to make the difference between their values
"""


def compareMetrics(firstObject=None, secondObject=None, workflow=None, stepnum=None):
    fields = []
    comparison_results = {}

    for stamp in firstObject:
        for wf in firstObject[stamp]:
            for step in firstObject[stamp][wf]:
                fields = firstObject[stamp][wf][step].keys()
                break
            break
        break

    for f in fields:
        comparison_results.update({f: []})

    for stamp in firstObject:
        for wf in firstObject[stamp]:
            if workflow:
                if float(wf) != float(workflow):
                    continue
            for step in firstObject[stamp][wf]:
                if stepnum:
                    # print stepnum, step
                    if str(stepnum) != str(step):
                        continue
                for field in firstObject[stamp][wf][step]:
                    # print field
                    if (
                        stamp in secondObject
                        and wf in secondObject[stamp]
                        and step in secondObject[stamp][wf]
                        and field in secondObject[stamp][wf][step]
                    ):
                        first_metric = firstObject[stamp][wf][step][field]
                        second_metric = secondObject[stamp][wf][step][field]

                        if field.startswith("rss"):
                            if second_metric is 0:
                                continue  # sometimes the result is zero even when the exit_code is non 0
                            # difference = 100 - ( float( float(first_metric) / float(second_metric) ) * 100 )
                            difference = int((first_metric - second_metric) / 1048576)
                        else:
                            difference = first_metric - second_metric

                        comparison_results[field].append(difference)

    return comparison_results


if __name__ == "__main__":
    opts = None
    release = None
    fields = ["time", "rss_max", "cpu_avg", "rss_75", "rss_25", "rss_avg"]

    arch = "slc7_amd64_gcc700"
    days = int(sys.argv[5])
    page_size = 0
    limit = 20

    release_one = sys.argv[1]
    release_two = sys.argv[2]
    archone = sys.argv[3]
    archtwo = sys.argv[4]
    wf_n = None
    step_n = None
    if len(sys.argv) > 6:
        wf_n = sys.argv[6]
    if len(sys.argv) > 7:
        step_n = sys.argv[7]
    print(wf_n, step_n)

    json_out_first = getWorkflowStatsFromES(release_one, archone, days, page_size)
    json_out_second = getWorkflowStatsFromES(release_two, archtwo, days, page_size)

    filtered_first = filterElasticSearchResult(json_out_first, fields)
    filtered_second = filterElasticSearchResult(json_out_second, fields)

    comp_results = compareMetrics(filtered_first, filtered_second, wf_n, step_n)
    # print json.dumps(comp_results, indent=2, sort_keys=True, separators=(',', ': '))

    for hist in comp_results:
        print(hist)
        histo = TH1F(
            hist, release_one + " - " + release_two + "[" + hist + "]", 100000, -5000, 5000
        )

        if hist.startswith("rss"):
            histo.GetXaxis().SetTitle("Difference in MB")
            # print 'title set for', hist
        if hist is "time":
            histo.GetXaxis().SetTitle("Difference in seconds")
        if hist.startswith("cpu"):
            histo.GetXaxis().SetTitle("Difference in cpu time")

        for i in comp_results[hist]:
            histo.Fill(i)
        histo.SaveAs(hist + ".root")

    # setup any CMSSW first (to get pyROOT in path)
    # example usage:
    # python getWorkflowStatsFromES.py CMSSW_10_5_ROOT6_X CMSSW_10_5_ROOT614_X slc7_amd64_gcc700 slc7_amd64_gcc700 14
