#!/usr/bin/env python3
import os, glob, sys, re, json
from datetime import datetime
from es_utils import send_payload
from cmsutils import cmsswIB2Week
from hashlib import sha1

def get_current_time():
    """Returns current time in milliseconds."""
    current_time = datetime.utcnow() - datetime(1970, 1, 1)
    current_time = round(current_time.total_seconds() * 1000)
    return current_time

def extract_packages(package_file):
    """Extracts package information from json file."""
    with open(package_file, "r") as f:
        package_data = json.load(f)

    package_dict = {}
    for package_key in package_data:
        package_info = package_data[package_key]
        package_name = package_info["name"]

        if process_type == "release":
            package_version = package_info["version"]
            package_version = package_version.rsplit("-", 1)[0]
        else:
            package_version = package_info["realversion"]

        package_dict[package_name] = package_version
    return package_dict

def parse_ib_folder_name(folder_name):
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

def parse_releases_path(path):
    architecture_pattern = r"/cms/([^/]+)/"
    version_pattern = r"/([^/]+)\.json$"
    date = ""

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

    return architecture, release_name, release_cycle, flavor, date

def extract_and_upload(directory):
    result = {}
    files = glob.glob(directory)
    for package_file in files:
        print("--> Processing file: ", package_file)
        if process_type == "release":
            architecture, name, release_cycle, flavor, date = parse_releases_path(file_path)
            index = "cmssw-pkginfo"
            if architecture != "Not found" and release_name != "Not found":
                packages = extract_packages(package_file)
        else:
            release_cycle, flavor, date = parse_folder_name(package_file.split("/")[6])
            architecture = package_file.split("/")[7]
            name = package_file.split("/")[6]
            weeknum, _ = cmsswIB2Week(name, 0)
            index = "cmssw-pkginfo-" + str(weeknum)
            packages = extract_packages(package_file)

        for package in packages:
            payload = {
                "name": name,
                "release_cycle": release_cycle,
                "flavor": flavor,
                "date": date,
                "architecture": architecture,
                "@timestamp": get_current_time(),
                package: packages[package]
            }

            unique_id = f"{release_cycle}_{flavor}_{date}_{architecture}_{package}"
            id = sha1(unique_id.encode("utf-8")).hexdigest()
            document = "cmssw-pkginfo"
            # Upload one entry per package
            print("Uploading to index " + index + " ...")
            #send_payload(index, document, id, json.dumps(payload))
    return result


process_type = sys.argv[1]

if process_type == "release":
    print("Processing Releases...")
    directory = "/data/cmssw/repos/cms/*_*_*/*/WEB/*/cms+cmssw+CMSSW*.json" # cmsrep path
else: # integration builds
    print("Processing IBs...")
    directory = "/data/sdt/SDT/jenkins-artifacts/build-any-ib/*/*_*_*/*/DEPS/cmssw-ib.json" # cmssdt path

extract_and_upload(directory)
