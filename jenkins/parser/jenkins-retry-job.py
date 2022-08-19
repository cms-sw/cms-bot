#!/usr/bin/env python3

import argparse
import functools
import re
import os
import xml.etree.ElementTree as ET

# Get job name and build number to retry
parser = argparse.ArgumentParser()
parser.add_argument("job_to_retry", help="Jenkins job to retry")
parser.add_argument("build_to_retry", help="Build number to retry")
parser.add_argument("current_build_number", help="Current build number")
args = parser.parse_args()
job_to_retry = args.job_to_retry
build_to_retry = args.build_to_retry
current_build_number = args.current_build_number

retry_counter_value = ""

# Assuming we are in the workspace/<job-name> directory, get all build
builds_dir = os.environ.get("HOME") + "/builds"

# Construct path to the logs
build_path = functools.reduce(os.path.join, [builds_dir, job_to_retry, build_to_retry])

print(
    "Retrying job "
    + job_to_retry
    + " build number "
    + build_to_retry
    + " in "
    + build_path
    + " ..."
)


def findParametersAction(root):
    """ It finds Jenkins parameters under section ParametersAction in xml file."""
    if root.tag == "parameters":
        return root
    for x in root:
        p = findParametersAction(x)
        if p is not None:
            return p
    return None


def getParameters(root, payload):
    """ Append Jenkins parameters of the form parameter=value (n.text=v.text) elements to a list."""
    n = root.find("name")
    if n is not None:
        if n.text is None:
            return
        v = root.find("value")
        if v is not None:
            if v.text is not None:
                payload.append(n.text + "=" + str(v.text))
        if "RETRY_COUNTER" in n.text:
            retry_counter_value = int(v.text)
    else:
        for x in root:
            getParameters(x, payload)


tree = ET.parse(os.path.join(build_path, "build.xml"))
root = tree.getroot()
pa = findParametersAction(root)

jenkins_params_values = []

if pa is not None:
    getParameters(pa, jenkins_params_values)

# Check that the retry counter is present, if not create one, if present update it
if retry_counter_value != "":
    # Check maximum number of retries and update counter
    max_retries = 3
    try:
        assert retry_counter_value < max_retries, (
            "This job is failing for " + str(max_retries) + " consecutive times..."
        )
    except AssertionError:
        update_label = (
            os.environ.get("JENKINS_CLI_CMD")
            + " set-build-description "
            + job_to_retry
            + " "
            + build_to_retry
            + " 'Maximum\ retries\ exceeded!'"
        )
        print(update_label)
        os.system(update_label)
        raise

    retry_counter_update = retry_counter_value + 1
    jenkins_params_values.append("RETRY_COUNTER=" + str(retry_counter_update) + "\n")
else:
    retry_counter_update = 1
    jenkins_params_values.append("RETRY_COUNTER=" + str(retry_counter_update) + "\n")

print("... with the following job parameters:")

# Construct property file
os.system("touch parameters.txt && chmod 777 parameters.txt")
with open("parameters.txt", "w") as propfile:
    for param in jenkins_params_values:
        print(param + "\n")
        propfile.write(param + "\n")

# Format retry label
times = "time" if retry_counter_update == 1 else "times"

label = (
    "Retried'\ '"
    + str(retry_counter_update)
    + "'\ '"
    + times
    + "'\ 'by'\ 'retry'\ 'job'\ '#"
    + str(current_build_number)
)

update_label = (
    os.environ.get("JENKINS_CLI_CMD")
    + " set-build-description "
    + job_to_retry
    + " "
    + build_to_retry
    + " "
    + label
)
print(update_label)
os.system(update_label)
