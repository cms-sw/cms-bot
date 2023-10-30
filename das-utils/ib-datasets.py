#!/usr/bin/env python
from os.path import dirname, abspath
from sys import argv
from time import time
import json, sys

cmsbot_dir = None
if __file__:
    cmsbot_dir = dirname(dirname(abspath(__file__)))
else:
    cmsbot_dir = dirname(dirname(abspath(argv[0])))
sys.path.insert(0, cmsbot_dir)

from es_utils import es_query
from _py2with3compatibility import run_cmd

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser(usage="%prog ")
    parser.add_option(
        "-r", "--release", dest="release", help="Release filter", type=str, default=".*"
    )
    parser.add_option(
        "-a",
        "--architecture",
        dest="arch",
        help="SCRAM_ARCH filter. Production arch for a release cycle is used if found otherwise slc6_amd64_gcc530",
        type=str,
        default=None,
    )
    parser.add_option(
        "-d", "--days", dest="days", help="Files access in last n days", type=int, default=7
    )
    parser.add_option("-j", "--job", dest="job", help="Parallel jobs to run", type=int, default=4)
    parser.add_option(
        "-p",
        "--page",
        dest="page_size",
        help="Page size, default 0 means no page and get all data in one go",
        type=int,
        default=0,
    )
    opts, args = parser.parse_args()

    if not opts.arch:
        if opts.release == ".*":
            opts.arch = ".*"
        else:
            script_path = abspath(dirname(argv[0]))
            err, out = run_cmd(
                "grep 'RELEASE_QUEUE=%s;' %s/config.map | grep -v 'DISABLED=1;' | grep 'PROD_ARCH=1;' | tr ';' '\n' | grep 'SCRAM_ARCH=' | sed 's|.*=||'"
                % (opts.release, script_path)
            )
            if err:
                opts.arch = "slc6_amd64_gcc530"
            else:
                opts.arch = out
    if opts.release != ".*":
        opts.release = opts.release + ".*"

    end_time = int(time() * 1000)
    start_time = end_time - int(86400 * 1000 * opts.days)
    query = "release:/%s/ AND architecture:/%s/" % (opts.release.lower(), opts.arch)
    es_data = es_query("ib-dataset-*", query, start_time, end_time, scroll=True, fields=["lfn"])
    print(json.dumps(es_data, indent=2, sort_keys=True, separators=(",", ": ")))
