#!/usr/bin/env python3

from collections import defaultdict
from categories import CMSSW_CATEGORIES, CMSSW_L2, CMSSW_ORP
import json

# Generates a json file sumarizing the categories, their packages, and conveners
# it asumes that categories.py from https://raw.githubusercontent.com/cms-sw/cms-bot/HEAD/categories.py
# is already downloaded

# ------------------------------------------------------------------------------
# Global Variables
# -----------------------------------------------------------------------------
OUTPUT_FILE = "categories.json"

# ------------------------------------------------------------------------------
# Start of execution
# -----------------------------------------------------------------------------

all_categories = list(CMSSW_CATEGORIES["cmssw"].keys())
# schema of categories_to_people:
# {
#   "<category>" : [ "<person1>" , "person2" , ... , "personN" ]
# }
categories_to_people = defaultdict(list)

for person in list(CMSSW_L2.keys()):
    categories = CMSSW_L2[person]
    for cat in categories:
        categories_to_people[cat].append(person)

print("----------------")
print(categories_to_people)

output = {}
output["people_to_categories"] = CMSSW_L2
output["categories_to_people"] = categories_to_people
output["categories_to_packages"] = CMSSW_CATEGORIES
output["ORP"] = CMSSW_ORP

with open(OUTPUT_FILE, "w") as out_json:
    json.dump(output, out_json, indent=4)
