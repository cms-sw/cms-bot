import json
import os

jobs_config_path = "jobs-config.json"
error_types = []

with open(jobs_config_path, "r") as jobs_file:
    jobs_object = json.load(jobs_file)
    jenkins_jobs = jobs_object["jobsConfig"]["jenkinsJobs"]
    error_msg = jobs_object["jobsConfig"]["errorMsg"]


print("[TEST 1]: Checking that all jobs defined in jobs-config.json exist in Jenkins ...")
job_names = [jenkins_jobs[job_id]["jobName"] for job_id in range(len(jenkins_jobs))]

for job in job_names:
    exit_code = os.system(
        "ssh -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i /var/lib/jenkins/.ssh/id_rsa-openstack -l localcli -p 8090 localhost get-job "
        + job
        + " > /dev/null"
    )
    assert exit_code == 0, "Job " + job + " does not exists in Jenkins"
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
    "retryBuild",
    "nodeOff",
    "nodeReconnect",
]  # TODO: Find a better way to get all valid actions
defined_actions = [
    error_msg[error_category]["action"] for error_category in error_msg.keys()
]
# Check that valid_actions contains contains all defined actions
assert all(
    item in valid_actions for item in defined_actions
), "Defined action does not correspond to a valid action"
print("[TEST 3]: ... OK")
