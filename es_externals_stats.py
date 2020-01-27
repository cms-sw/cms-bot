#!/usr/bin/env python
from __future__ import print_function
from cmsutils import percentile
from es_utils import send_payload
from sys import argv
import json
from hashlib import sha1

def get_average_stats_for_external(stats_dict, opts_dict, params=None, cpu_normalize=1):

    sdata = None
    try:
        stats = stats_dict
        xdata = {}
        for stat in stats:
            for item in stat:
                try:
                    xdata[item].append(stat[item])
                except:
                    xdata[item] = []
                    xdata[item].append(stat[item])
        sdata = {}
        if params:
            for p in params: sdata[p] = params[p]
        for x in xdata:
            data = sorted(xdata[x])
            if x in ["time", "num_threads", "processes", "num_fds"]:
                sdata[x] = data[-1]
                continue
            if not x in ["rss", "vms", "pss", "uss", "shared", "data", "cpu"]: continue
            dlen = len(data)
            if (x == "cpu") and (cpu_normalize > 1) and (data[-1] > 100):
                data = [d / cpu_normalize for d in data]
            for t in ["min", "max", "avg", "median", "25", "75", "90"]: sdata[x + "_" + t] = 0
            if dlen > 0:
                sdata[x + "_min"] = data[0]
                sdata[x + "_max"] = data[-1]
                if dlen > 1:
                    dlen2 = int(dlen / 2)
                    if (dlen % 2) == 0:
                        sdata[x + "_median"] = int((data[dlen2 - 1] + data[dlen2]) / 2)
                    else:
                        sdata[x + "_median"] = data[dlen2]
                    sdata[x + "_avg"] = int(sum(data) / dlen)
                    for t in [25, 75, 90]:
                        sdata[x + "_" + str(t)] = int(percentile(t, data, dlen))
                else:
                    for t in ["25", "75", "90", "avg", "median"]:
                        sdata[x + "_" + t] = data[0]

    except Exception as e: print(e.message)
    return sdata

# give a list of relevant keys to get from the options dictionary, could be all or limited
def create_index_name_from_args(opts_dict=None, list_of_keys=None):
    if opts_dict and list_of_keys:
        result_string = ''
        for k in list_of_keys: result_string = result_string+str(opts_dict[k])
        return sha1(result_string).hexdigest()
    else:
        return None

if __name__ == "__main__":

    stats_json_arg = argv[1]
    opts_json_arg = argv[2]
    week = argv[3]

    with open(stats_json_arg, "r") as stats_json_file: stats_json = json.load(stats_json_file)
    with open(opts_json_arg, "r") as opts_json_file: opts_json = json.load(opts_json_file)

    index_name = "externals_build_runtime_stats_summary_testindex"
    doc = "external-runtime-stats-summary_testindex"
    index_sha1 = create_index_name_from_args(opts_json, opts_json.keys())
    payload = get_average_stats_for_external(stats_json, opts_json, None, 1)
    payload.update(opts_json)
    print('externals stats: ', stats_json_arg, 'options json: ', opts_json, 'week is: ', week)
    try:
        print(json.dumps(payload, indent=1, sort_keys=True))
    #   #send_payload(index+'-'+week,doc, index_sha1,json.dumps(payload))
    except Exception as e: print(e.message)
    #print('index sha is: ', index_sha1)

