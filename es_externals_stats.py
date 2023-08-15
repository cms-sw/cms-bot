#!/usr/bin/env python3
from sys import argv
from es_utils import es_send_external_stats

if __name__ == "__main__":

    stats_json_f = argv[1]
    opts_json_f = argv[2]
    es_send_external_stats(stats_json_f, opts_json_f, 1)
