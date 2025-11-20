#!/usr/bin/env python3
from sys import argv
from es_utils import es_send_external_stats

es_send_external_stats(argv[3], argv[1], argv[2], 1)
