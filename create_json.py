#!/usr/bin/env python3

import sys, re, json
from os import environ, popen
from os.path import dirname, realpath
from optparse import OptionParser

parser = OptionParser()
parser.add_option('--logfile')
parser.add_option('--jsonfile')
(options, args) = parser.parse_args()

def extract_data(inputfile):
  list_of_dicts = []
  with open(inputfile, 'r') as file:
    first_char = file.read(1)
    if not first_char: print("Error: Input file is empty"), sys.exit(1)
    pattern = re.compile('^([a-z]+)\+([\w-]+)\+([\w.-]+)\s\(([\w]+)\)')
    matched_lines = [pattern.match(l) for l in file.readlines()]
    for line in matched_lines: 
      if line: 
        list_of_dicts.append(dict(
          package_type = line.group(1),
          name = line.group(2),
          ver_suffix = line.group(3),
          hashtag = line.group(4)
        ))
  return json.dumps(list_of_dicts, sort_keys=True, indent=2)


with open(options.jsonfile, 'w' ) as file:
  file.write(extract_data(options.logfile))
