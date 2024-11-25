#!/usr/bin/env python3
import os, glob
import re
import json
from datetime import datetime
from es_utils import send_payload
from hashlib import sha1

JENKINS_PREFIX = "jenkins"
try:
    JENKINS_PREFIX = os.environ["JENKINS_URL"].strip("/").split("/")[-1]
except:
    JENKINS_PREFIX = "jenkins"

def extract_packages(package_file):
    with open(package_file, "r") as f:
        package_data = json.load(f)

    # Dictionary to store package name and version pairs
    package_dict = {}

    for package_key in package_data:
        package_info = package_data[package_key]
        package_name = package_info["name"]
        package_version = package_info["realversion"]

        package_dict[package_name] = package_version

    return package_dict

def parse_folder_name(folder_name):
    match = re.match(r"^(CMSSW_\d+_\d+)(_?[^_]+)?(_X)?_(\d{4}-\d{2}-\d{2}-\d{4})$", folder_name)
    if not match:
        print(f"Folder name '{folder_name}' doesn't match the expected pattern")
        return None
    version = match.group(1)
    flavor_part = match.group(2) if match.group(2) else ""
    flavor = flavor_part.lstrip("_")
    if not flavor:
        flavor = "X"
    elif flavor == "X":
        flavor = "DEFAULT"
    date = match.group(4)
    return version, flavor, date

def get_current_time():
    """Returns current time in milliseconds."""
    current_time = datetime.utcnow() - datetime(1970, 1, 1)
    current_time = round(current_time.total_seconds() * 1000)
    return current_time

def extract_and_upload(directory):
    result = {}

    files = glob.glob(directory)
    for package_file in files:
        print("--> Processing file: ", package_file)
        packages = extract_packages(package_file)

        release_cycle, flavor, date = parse_folder_name(package_file.split("/")[6])
        architecture = package_file.split("/")[7]
        for package in packages:
            payload = {
                "ib_name": package_file.split("/")[6],
                "release_cycle": release_cycle,
                "flavor": flavor,
                "date": date,
                "architecture": architecture,
                "@timestamp": get_current_time(),
                package: packages[package],
                "jenkins_server": JENKINS_PREFIX,
            }
            unique_id = f"{release_cycle}_{flavor}_{date}_{architecture}_{package}"
            id = sha1(unique_id.encode("utf-8")).hexdigest()
            index = "cmssw-ib-pkginfo"
            document = "cmssw-ib-pkginfo"
            # Upload one entry per package
            send_payload(index, document, id, json.dumps(payload))
    return result

directory = "/data/sdt/SDT/jenkins-artifacts/build-any-ib/*/*_*_*/*/DEPS/cmssw-ib.json"
result = extract_and_upload(directory)
