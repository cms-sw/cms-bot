#!/usr/bin/env python

# A script which deletes elasticsearch logs when they are older that the specified amount
# of units.


# Each config line has the folloing format:
#
# - Format of the index, including the datetime part. This will
#   be used to determine the age of the index.
# - The time period in which an index is considered to be valid.
#   You can use y, m, d , H, M suffix to specify years, months,
#   days, hours, minutes.
# - The action to perform when the index is old enough. For the moment it can be
#     - delete: delete the index.

from __future__ import print_function
from argparse import ArgumentParser
from _py2with3compatibility import run_cmd
from datetime import datetime
import re
from os import getenv

CONFIG = [
    ["mesos-offers-%Y.%m.%d", "1M", "delete"],
    ["mesos-info-%Y.%m.%d.%H%M", "1H", "delete"],
    ["mesos-info-%Y.%m.%d", "2d", "delete"],
    ["mesos-logs-%%{loglevel}-%Y.%m.%d", "2d", "delete"],
    ["mesos-warning-%Y.%m.%d", "1d", "delete"],
    ["mesos-error-%Y.%m.%d", "1d", "delete"],
    ["mesos-logs-i-%Y.%m.%d", "1d", "delete"],
    ["mesos-logs-w-%Y.%m.%d", "1d", "delete"],
    ["mesos-logs-e-%Y.%m.%d", "1d", "delete"],
    ["mesos-logs-f-%Y.%m.%d", "1d", "delete"],
    ["ib-files-%Y.%m", "1m", "delete"],
    ["stats-condweb-%Y.%m.%d", "2d", "delete"],
    ["stats-condweb-access-%Y.%m.%d", "2d", "delete"],
    ["stats-condweb-error-%Y.%m", "1m", "delete"],
    ["ib-matrix.%Y.%m", "1m", "delete"],
    ["ib-matrix.%Y-%W-%w", "14d", "delete"],
    ["ib-scram-stats-%Y.%m.%d", "7d", "delete"],
]


def format(s, **kwds):
    return s % kwds


timeunits = {
    "Y": 60 * 60 * 24 * 356,
    "m": 60 * 60 * 24 * 30,
    "d": 60 * 60 * 24,
    "H": 60 * 60,
    "M": 60,
}

if __name__ == "__main__":
    # First get all the available indices
    parser = ArgumentParser()
    parser.add_argument("--proxy", help="the proxy to use")
    parser.add_argument("--server", help="the elasticsearch entrypoint")
    parser.add_argument("--user", help="user to be used for authentication")
    parser.add_argument(
        "--auth-file", dest="authFile", help="file containing the authentication token"
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        dest="dryrun",
        action="store_true",
        default=False,
        help="the elasticsearch entrypoint",
    )
    args = parser.parse_args()
    proxy_string = ""
    if args.proxy:
        proxy_string = "--socks5-hostname " + args.proxy

    if args.user and args.authFile:
        user_string = "--user %s:%s" % (args.user, open(args.authFile).read().strip())
    elif getenv("ES_AUTH"):
        user_string = "--user %s" % getenv("ES_AUTH")

    cmd = format(
        "curl -s %(proxy_string)s %(server)s/_cat/indices " "%(user_string)s",
        proxy_string=proxy_string,
        server=args.server,
        user_string=user_string,
    )
    err, out = run_cmd(cmd)
    if err:
        print("Error while getting indices")
        print(out)
        exit(0)
    indices = [re.split("[ ]+", l)[2] for l in out.split("\n")]
    for c in CONFIG:
        pattern, timeout, action = c
        m = re.match("([0-9]*)([YmdHM])", timeout)
        if not m:
            print("Malformed timeout %s" % timeout)
            exit(1)
        time, unit = m.groups()
        timedelta = int(time) * timeunits[unit]
        for index in indices:
            try:
                d = datetime.strptime(index, pattern)
            except ValueError as e:
                continue
            print(index, "matches", pattern)
            now = datetime.now()
            td = now - d
            total_seconds = (
                td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6
            ) / 10**6
            if total_seconds < timedelta:
                print(index, "is recent enough. Keeping.")
                continue
            print(index, "is older than", timeout, ". Deleting")
            if not args.dryrun:
                cmd = format(
                    "curl -s -X DELETE %(proxy_string)s %(server)s/%(index)s" " %(user_string)s",
                    proxy_string=proxy_string,
                    server=args.server,
                    index=index,
                    user_string=user_string,
                )
                err, out = run_cmd(cmd)
                if err:
                    print("Error while deleting.")
                    print(out)
                    exit(1)
                print(index, "deleted.")
