#!/usr/bin/env python3

import argparse
import functools
import re
import os
import xml.etree.ElementTree as ET
import datetime

import actions
import helpers

# Get job name and build number to retry
parser = argparse.ArgumentParser()
parser.add_argument("job_to_retry", help="Jenkins job to retry")
parser.add_argument("build_to_retry", help="Build number to retry")
parser.add_argument("parser_action", help="Action taken by parser job")
parser.add_argument("error_message", type=str, help="Error message found in build log")
parser.add_argument("current_build_number", help="Current build number")
args = parser.parse_args()
job_to_retry = args.job_to_retry
build_to_retry = args.build_to_retry
parser_action = args.parser_action
regex = args.error_message.replace("&", " ")
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
    else:
        for x in root:
            getParameters(x, payload)


tree = ET.parse(os.path.join(build_path, "build.xml"))
root = tree.getroot()
pa = findParametersAction(root)

jenkins_params_values = []

if pa is not None:
    getParameters(pa, jenkins_params_values)

# Get RETRY_COUNTER, if present
r = re.compile("RETRY_COUNTER=.*")
retry_counter = list(filter(r.match, jenkins_params_values))

# If retry counter is present, get its value and update it. If not, create one.
if retry_counter != []:
    retry_counter_value = int(retry_counter[0].split("=")[1])

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
    jenkins_params_values.remove(retry_counter[0])  # Remove old value from params
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


# Update static webpage
tracker_path = (
    os.environ.get("HOME") + "/builds/jenkins-test-parser-monitor/parser-web-info.html"
)
job_url = os.environ.get("JENKINS_URL") + "job/" + job_to_retry + "/" + build_to_retry
retry_url = (
    os.environ.get("JENKINS_URL") + "job/jenkins-test-retry/" + current_build_number
)

retry_url_file_path = (
    os.environ.get("HOME") + "/builds/jenkins-test-parser-monitor/json-retry-info.json"
)
actions.update_retry_link_cmssdt_page(
    retry_url_file_path, job_to_retry, build_to_retry, retry_url
)

# Format retry label depending on parser action
times = "time" if retry_counter_update == 1 else "times"

retry_label = (
    "Job'\ 'retried'\ '"
    + str(retry_counter_update)
    + "'\ '"
    + times
    + "'\ 'by'\ 'retry'\ 'job'\ '#"
    + str(current_build_number)
)

nodeoff_label = (
    "Node'\ 'marked'\ 'as'\ 'offline'\ 'and'\ 'job'\ 'retried.'\ 'Please,'\ 'take'\ 'the'\ 'appropiate'\ 'action'\ 'and'\ 'relaunch'\ 'the'\ 'node.'\ 'Also,'\ 'make'\ 'sure'\ 'that'\ 'the'\ 'job'\ 'is'\ 'running'\ 'fine'\ 'now.'\ 'Job'\ 'has'\ 'been'\ 'retried'\ '"
    + str(retry_counter_update)
    + "'\ '"
    + times
    + "'\ 'by'\ 'retry'\ 'job'\ '#"
    + str(current_build_number)
)

nodereconnect_label = (
    "Node'\ 'has'\ 'been'\ 'forced'\ 'to'\ 'reconnect'\ 'and'\ 'job'\ 'has'\ 'been'\ 'retried.'\ 'Please,'\ 'make'\ 'sure'\ 'that'\ 'the'\ 'node'\ 'is'\ 'in'\ 'good'\ 'state'\ 'and'\ 'job'\ 'is'\ 'running'\ 'fine'\ 'now.'\ 'Job'\ 'has'\ 'been'\ 'retried'\ '"
    + str(retry_counter_update)
    + "'\ '"
    + times
    + "'\ 'by'\ 'retry'\ 'job'\ '#"
    + str(current_build_number)
)

if "retry" in parser_action:
    label = retry_label
elif parser_action == "nodeOff":
    label = nodeoff_label
else:  # nodeReconnect
    label = nodereconnect_label

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
