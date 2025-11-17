#!/usr/bin/env python3
import sys, json
from es_utils import get_avg_externals_build_stats as get_stats

print(json.dumps(get_stats(arch=sys.argv[1])))
