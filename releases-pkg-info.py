#!/usr/bin/env python3
import os
import re
import json
from datetime import datetime
from es_utils import send_payload
from hashlib import sha1
import glob

JENKINS_PREFIX="jenkins"
try:    JENKINS_PREFIX=os.environ['JENKINS_URL'].strip("/").split("/")[-1]
except: JENKINS_PREFIX="jenkins"

def get_current_time():
    """Returns current time in milliseconds. """
    current_time = datetime.utcnow() - datetime(1970, 1, 1)
    current_time = round(current_time.total_seconds()*1000)
    return current_time

def extract_packages(package_file):
    with open(package_file, "r") as f:
        package_data = json.load(f)

    package_dict = {}
    for package_key in package_data:
        package_info = package_data[package_key]
        package_name = package_info["name"]
        full_version = package_info["version"]

        version_without_checksum = full_version.split("-")[0]
        package_dict[package_name] = version_without_checksum

    return package_dict

def parse_releases_path(path):
    architecture_pattern = r"/cms/([^/]+)/"
    version_pattern = r"/([^/]+)\.json$"

    architecture_match = re.search(architecture_pattern, path)
    if architecture_match:
        architecture = architecture_match.group(1)
    else:
        architecture = "Not found"

    version_match = re.search(version_pattern, path)
    if version_match:
        full_version = version_match.group(1)
        version_match = re.search(r"(CMSSW_\d+_\d+(_\d+)*)(_(.*))?", full_version)
        if version_match:
            release_cycle = version_match.group(1)
            flavor = version_match.group(4) if version_match.group(4) else ""
            release_name = f"{release_cycle}_{flavor}" if flavor else release_cycle
        else:
            release_cycle = "Not found"
            flavor = ""
            release_name = "Not found"
    else:
        release_cycle = "Not found"
        flavor = ""
        release_name = "Not found"

    print("--> Release cycle: ", release_cycle)
    return architecture, release_name, release_cycle, flavor

def process_and_index_releases_directory(directory):
    releases_info = {}
    files = glob.glob(directory)

    for file_path in files:
        print(file_path)
        architecture, release_name, release_cycle, flavor = parse_releases_path(
                file_path
        )

        if architecture != "Not found" and release_name != "Not found":
            packages = extract_packages(file_path)

            for package in packages:
                payload = {
                    "release_name": release_name,
                    "flavor": flavor,
                    "release_cycle": release_cycle,
                    "architecture": architecture,
                    "@timestamp": get_current_time(),
                    package: packages[package],
                    "jenkins_server": JENKINS_PREFIX
                }

                unique_id = f"{release_name}_{architecture}_{package}"
                id = sha1(unique_id.encode('utf-8')).hexdigest()

                index = "cmssw-releases-pkgs"
                document = "cmssw-releases-pkgs-info"
                send_payload(index,document,id,json.dumps(payload))
                print(payload)
    return releases_info

directory = '/data/cmssw/repos/cms/*_*_*/*/WEB/*/cms+cmssw+CMSSW*.json'
process_and_index_releases_directory(directory)
