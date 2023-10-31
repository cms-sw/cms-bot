#!/bin/env python
from datetime import datetime
import re, json
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("-i", "--input")
parser.add_argument("-o", "--output")
args = parser.parse_args()
fd_read = open(args.input, "r")

dict_store = {}
for line in fd_read:
    workflow = line.split("_")[0]
    match_date = re.findall(
        r"[A-Z]{3}\s+[\d]{2}\s+[\d]{2}:[\d]{2}:[\d]{2}\s+[\d]{4}", line, re.IGNORECASE
    )
    if len(match_date) != 2:
        continue

    t1 = datetime.strptime(match_date[1], "%b %d %H:%M:%S %Y")
    t2 = datetime.strptime(match_date[0], "%b %d %H:%M:%S %Y")
    delta = t2 - t1
    dict_store[workflow] = delta.seconds

fd_read.close
with open(args.output, "w") as outfile:
    json.dump(dict_store, outfile)
