#!/usr/bin/env python
from __future__ import print_function
from sys import argv
import json
from os import stat as tstat
from es_utils import es_send_external_stats

if __name__ == "__main__":

    stats_json_f = argv[1]
    opts_json_f = argv[2]
    with open(stats_json_f, "r") as stats_json_file: stats_json = json.load(stats_json_file)
    with open(opts_json_f, "r") as opts_json_file: opts_json = json.load(opts_json_file)
    file_stamp = int(tstat(stats_json_f).st_mtime)  # get the file stamp from the file
    week = str((file_stamp / 86400 + 4) / 7)
    es_send_external_stats(stats_json, opts_json, 1, week)
