import json
import os
import re
from subprocess import getstatusoutput
import time


jobs_config_path = "jenkins/parser/jobs-config.json"
error_types = []

with open(jobs_config_path, "r") as jobs_file:
    jobs_object = json.load(jobs_file)
    jenkins_jobs = jobs_object["jobsConfig"]["jenkinsJobs"]
    error_msg = jobs_object["jobsConfig"]["errorMsg"]


print("[TEST 1]: Checking that all jobs defined in jobs-config.json exist in Jenkins ...")
job_names = [jenkins_jobs[job_id]["jobName"] for job_id in range(len(jenkins_jobs))]

_, output = getstatusoutput(
    'curl -s https://raw.githubusercontent.com/cms-sw/cmssdt-wiki/master/jenkins_reports/All.md | grep "## \[.*\](.*"'
)
valid_job_names = [
    re.sub("\]\(.*", "", item.replace("## [", "")) for item in output.split("\n")
]
# Check that valid_job_names contains all elements of job_names
assert all(
    item in valid_job_names for item in job_names
), "Invalid job names have been defined in config file"
print("[TEST 1]: ... OK")


print("[TEST 2]: Checking that all error categories are correctly defined ...")
for job_id in range(len(jenkins_jobs)):
    error_types += jenkins_jobs[job_id]["errorType"]

# Check that error_msg.keys() contains all elements of error_types
assert all(
    item in list(error_msg.keys()) for item in list(set(error_types))
), "New error type is not defined as a category in section errorMsg"
print("[TEST 2]: ... OK")


print("[TEST 3]: Checking that the defined actions are valid ...")
valid_actions = [
    "retryNow",
    "retryLate"
    "nodeOff",
    "nodeReconnect",
]  # TODO: Find a better way to get all valid actions
defined_actions = [
    error_msg[error_category]["action"] for error_category in error_msg.keys()
]
# Check that valid_actions contains all defined actions
assert all(
    item in valid_actions for item in defined_actions
), "Defined action does not correspond to a valid action"
print("[TEST 3]: ... OK")

print("[TEST 4]: Checking that default sections are present ...")
default_fields = jobs_object["defaultConfig"].keys()
valid_fields = ["forceRetry", "allJobs"]  # TODO: Find a better way to get valid fields
assert all(
    item in valid_fields for item in default_fields
), "Defined default field does not correspond to a valid field. Only forceRetry and allJobs fields should be defined under defaultConfig."
print("[TEST 4]: ... OK")
