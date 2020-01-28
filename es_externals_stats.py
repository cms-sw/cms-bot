#!/usr/bin/env python
from __future__ import print_function
from sys import argv
import json
from os import stat as tstat
from es_utils import es_send_external_stats

if __name__ == "__main__":

    #stats_json_arg = argv[1]
    #opts_json_arg = argv[2]
    #with open(stats_json_arg, "r") as stats_json_file: stats_json = json.load(stats_json_file)
    #with open(opts_json_arg, "r") as opts_json_file: opts_json = json.load(opts_json_file)
    stats_json_f = "/home/mrodozov/Downloads/all/build_zstd/BUILD/slc7_amd64_gcc820/external/cmake/3.14.5-cms/cmake.json"
    opts_json_f = "/home/mrodozov/Downloads/all/build_zstd/BUILD/slc7_amd64_gcc820/external/cmake/3.14.5-cms/opts.json"
    with open(stats_json_f, "r") as stats_json_file: stats_json = json.load(stats_json_file)
    with open(opts_json_f, "r") as opts_json_file: opts_json = json.load(opts_json_file)
    file_stamp = int(tstat(stats_json_f).st_mtime)  # get the file stamp from the file
    week = str((file_stamp / 86400 + 4) / 7)
    index_name = "externals_build_runtime_stats_summary_testindex"
    doc_name= "external-runtime-stats-summary-document_testdoc"
    sdata = es_send_external_stats(stats_json, opts_json, 1, week, es_index_name=index_name, es_doc_name=doc_name)
    print(json.dumps(sdata, indent=1, sort_keys=True))