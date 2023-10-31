#!/usr/bin/env python3

import argparse
import datetime
import functools
import json
import os
import re
import time

import helpers
import actions


def process_build(build, job_dir, job_to_retry, error_list, retry_object, retry_delay):
    """Process finished build. If failed, check for known erros. If succeed, check if it is a retried build to update its description."""
    if helpers.grep(
        functools.reduce(os.path.join, [job_dir, build, "build.xml"]),
        "<result>FAILURE",
    ):
        check_and_trigger_action(
            build, job_dir, job_to_retry, error_list, retry_object, retry_delay
        )
    else:
        # Mark as retried
        actions.mark_build_as_retried(job_dir, job_to_retry, build)
        print("[" + job_to_retry + "] ... #" + str(build) + " OK")


def check_and_trigger_action(
    build_to_retry, job_dir, job_to_retry, error_list_action, retry_object, retry_delay
):
    """Check build logs and trigger the appropiate action if a known error is found."""
    build_dir_path = os.path.join(job_dir, build_to_retry)
    log_file_path = os.path.join(build_dir_path, "log")
    envvars_file_path = os.path.join(build_dir_path, "injectedEnvVars.txt")

    if not os.path.exists(log_file_path):
        return
    # TODO: Try not to load everything on memory
    text_log = open(log_file_path, errors="ignore")
    lines = text_log.readlines()
    text_log.close()

    job_url = os.environ.get("JENKINS_URL") + "job/" + job_to_retry + "/" + build_to_retry

    print("Parsing build #" + build_to_retry + " (" + job_url + ") ...")

    regex_flag = 0
    for error_and_action in error_list:
        regex_and_action = error_and_action.split(" - ")
        regex = regex_and_action[0]
        action = regex_and_action[1]
        for line in reversed(lines):
            if re.search(regex, line):
                print(
                    "... Found message " + regex + " in " + log_file_path + ". Taking action ..."
                )
                if "retry" in action:
                    actions.trigger_retry_action(
                        job_to_retry,
                        job_url,
                        build_to_retry,
                        build_dir_path,
                        action,
                        regex,
                        force_retry_regex,
                        retry_object,
                        retry_delay,
                    )
                else:
                    # Take action on the nodes
                    node_name = helpers.grep(envvars_file_path, "NODE_NAME=", True) or ""
                    node_name = node_name.split("=")[1].replace("\n", "")
                    job_url = (
                        os.environ.get("JENKINS_URL")
                        + "job/"
                        + job_to_retry
                        + "/"
                        + build_to_retry
                    )
                    node_url = os.environ.get("JENKINS_URL") + "computer/" + node_name
                    parser_url = (
                        os.environ.get("JENKINS_URL")
                        + "job/jenkins-test-parser/"
                        + parser_build_id
                    )

                    if action == "nodeOff":
                        if node_name not in affected_nodes:
                            affected_nodes.append(node_name)
                            actions.trigger_nodeoff_action(
                                job_to_retry, build_to_retry, job_url, node_name
                            )
                            actions.notify_nodeoff(
                                node_name,
                                regex,
                                job_to_retry,
                                build_to_retry,
                                job_url,
                                node_url,
                                parser_url,
                            )

                            # if "grid" in node_name:
                            #     print("Error found on a grid node!")
                            #     actions.trigger_create_gridnode_action(node_name)

                        actions.trigger_retry_action(
                            job_to_retry,
                            job_url,
                            build_to_retry,
                            build_dir_path,
                            action,
                            regex,
                            force_retry_regex,
                        )
                    elif action == "nodeReconnect":
                        if node_name not in affected_nodes:
                            affected_nodes.append(node_name)
                            actions.trigger_reconnect_action(
                                job_to_retry, build_to_retry, job_url, node_name
                            )
                            actions.notify_nodereconnect(
                                node_name,
                                regex,
                                job_to_retry,
                                build_to_retry,
                                job_url,
                                node_url,
                                parser_url,
                            )
                        actions.trigger_retry_action(
                            job_to_retry,
                            job_url,
                            build_to_retry,
                            build_dir_path,
                            action,
                            regex,
                            force_retry_regex,
                        )

                regex_flag = 1
                break
            if regex_flag == 1:
                break
        if regex_flag == 1:
            break

    with open(parser_info_path, "w") as processed_file:
        json.dump(processed_object, processed_file, indent=2)

    if regex_flag == 0:
        print("... no known errors were found.")
        # Update description to inform that no action has been taken
        actions.update_no_action_label(job_to_retry, build_to_retry, job_url)
        actions.update_cmssdt_page(
            html_file_path,
            job_to_retry,
            build_to_retry,
            "No error found. Please, take the appropiate action",
            job_url,
            "[ No action taken ]",
            "NoAction",
        )

        build_file_path = os.path.join(build_dir_path, "build.xml")
        display_name = helpers.grep(build_file_path, "<displayName>", True) or ""
        display_name = (
            display_name.replace("<displayName>", "")
            .replace("</displayName>", "")
            .replace("\n", "")
        )
        actions.notify_noaction(display_name, job_to_retry, build_to_retry, job_url)


def check_running_time(job_dir, build_to_retry, job_to_retry, max_running_time=18):
    """Check builds running time and notify in case it exceeds the maximum time defined (default max time = 18h)."""
    job_url = os.environ.get("JENKINS_URL") + "job/" + job_to_retry + "/" + build_to_retry
    parser_url = os.environ.get("JENKINS_URL") + "job/jenkins-test-parser/" + parser_build_id

    build_file_path = functools.reduce(os.path.join, [job_dir, build_to_check, "build.xml"])

    if not os.path.exists(build_file_path):
        print("[DEBUG] No time check for ", job_url)
        processed_object["parserInfo"]["runningBuilds"][job_to_retry].pop(build_to_retry)
        return
    if helpers.grep(build_file_path, "<result>"):
        print("[DEBUG] No time check for ", job_url)
        processed_object["parserInfo"]["runningBuilds"][job_to_retry].pop(build_to_retry)
        return

    if (
        processed_object["parserInfo"]["runningBuilds"][job_to_retry][build_to_retry]
        == "emailSent"
    ):
        print(
            "... Email notification already send for build #"
            + build_to_retry
            + " ("
            + job_url
            + ")."
        )
        return

    start_timestamp = helpers.grep(build_file_path, "<startTime>", True) or ""
    start_timestamp = start_timestamp.replace("<startTime>", "").replace("</startTime>", "")

    display_name = helpers.grep(build_file_path, "<displayName>", True) or ""
    display_name = (
        display_name.replace("<displayName>", "").replace("</displayName>", "").replace("\n", "")
    )

    start_datetime = datetime.datetime.fromtimestamp(int(start_timestamp) / 1000)
    now = datetime.datetime.now()
    duration = now - start_datetime

    if duration > datetime.timedelta(hours=max_running_time):

        print(
            "Build #"
            + build_to_retry
            + " ("
            + job_url
            + ") has been running for more than "
            + str(max_running_time)
            + " hours!"
        )

        processed_object["parserInfo"]["runningBuilds"][job_to_retry][build_to_retry] = "emailSent"

        # Mark as notified
        actions.notify_pendingbuild(
            display_name,
            build_to_retry,
            job_to_retry,
            duration,
            job_url,
            parser_url,
        )

    else:
        print(
            "... Build #"
            + build_to_retry
            + " ("
            + job_url
            + ")"
            + " has been running for "
            + str(duration)
            + " hours ... OK"
        )


if __name__ == "__main__":

    # Set start time
    start_time = datetime.datetime.now()

    # Parse the build id of the current job
    parser = argparse.ArgumentParser()
    parser.add_argument("parser_build_id", help="Input current build id from Jenkins env vars")
    args = parser.parse_args()
    parser_build_id = args.parser_build_id

    # Define paths:
    jobs_config_path = "cms-bot/jenkins/parser/jobs-config.json"  # This file matches job with their known errors and the action to perform
    builds_dir = os.environ.get("HOME") + "/builds"  # Path to the actual build logs
    parser_info_path = (
        os.environ.get("HOME") + "/builds/jenkins-test-parser/parser-info.json"
    )  # This file keeps track of the last log processed and the pending builds
    html_file_path = (
        os.environ.get("HOME") + "/builds/jenkins-test-parser-monitor/json-web-info.json"
    )
    retry_queue_path = os.environ.get("HOME") + "/builds/jenkins-test-parser/retry_queue.json"

    # Get job-config info - always present (cloned from github)
    with open(jobs_config_path, "r") as jobs_file:
        jobs_object = json.load(jobs_file)
        jenkins_jobs = jobs_object["jobsConfig"]["jenkinsJobs"]

    # Get parser-info from previous run
    try:
        with open(parser_info_path, "r") as processed_file:  # Get last parsed object just once
            processed_object = json.load(processed_file)
    except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
        print(f"Error occurred: {str(e)}")
        print("Restoring parser-info.json file...")
        with open(parser_info_path, "w") as json_file:
            processed_object = {"parserInfo": {"lastRevision": {}, "runningBuilds": {}}}
            json.dump(processed_object, json_file, indent=2)

    # Get retry queue
    try:
        with open(retry_queue_path, "r") as retry_file:
            retry_object = json.load(retry_file)
            retry_entries = retry_object["retryQueue"]
    except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
        print(f"Error occurred: {str(e)}")
        print("Restoring retry_queue.json file...")
        with open(retry_queue_path, "w") as json_file:
            retry_object = {"retryQueue": {}}
            json.dump(retry_object, json_file, indent=2)
            retry_entries = retry_object["retryQueue"]

    T = 1
    time_check = True

    while True:
        current_time = datetime.datetime.now()
        elapsed_time = current_time - start_time
        # Restart list of affected nodes in each iteration
        affected_nodes = []

        # Iterate over all jobs in jobs_file
        for job_id in range(len(jenkins_jobs)):
            job_to_retry = jenkins_jobs[job_id]["jobName"]
            try:
                max_running_time = int(jenkins_jobs[job_id]["maxTime"])
            except KeyError:
                # The default max running time is 18h for all builds
                max_running_time = 18
            try:
                retry_delay = int(jenkins_jobs[job_id]["retryTime"])
            except KeyError:
                # The default delay time is 10 min for all builds
                retry_delay = 10

            # print("[" + job_to_retry + "] Processing ...")
            job_dir = os.path.join(builds_dir, job_to_retry)
            error_list, force_retry_regex = helpers.get_errors_list(jobs_object, job_id)

            # Get revision number
            try:
                latest_revision = processed_object["parserInfo"]["lastRevision"][job_to_retry]
            except KeyError:
                latest_revision = 0
                processed_object["parserInfo"]["lastRevision"][job_to_retry] = "0"

            # Take info from rotation list
            try:
                total_running_builds = list(
                    processed_object["parserInfo"]["runningBuilds"][job_to_retry].keys()
                )
            except KeyError:
                processed_object["parserInfo"]["runningBuilds"][job_to_retry] = dict()
                total_running_builds = []

            # Look for untracked builds
            missing_builds = helpers.get_missing_builds(
                job_dir, total_running_builds, latest_revision
            )
            if missing_builds:
                print(
                    "["
                    + job_to_retry
                    + "] Builds #"
                    + str(", #".join(missing_builds))
                    + " have finished. Processing ..."
                )
                for build in sorted(missing_builds):
                    process_build(
                        build,
                        job_dir,
                        job_to_retry,
                        error_list,
                        retry_object,
                        retry_delay,
                    )

                # Update last processed log only if greater than current revision number
                max_latest_revision = max([int(build_id) for build_id in missing_builds])
                if max_latest_revision > int(latest_revision):
                    processed_object["parserInfo"]["lastRevision"][
                        job_to_retry
                    ] = max_latest_revision

            # Update running builds checking > last revision number
            new_running_builds = helpers.get_running_builds(job_dir, latest_revision)

            for build in new_running_builds:
                if build not in total_running_builds:
                    total_running_builds.append(build)

            # Update running builds in the original object
            for build in sorted(total_running_builds):
                if (
                    build
                    not in processed_object["parserInfo"]["runningBuilds"][job_to_retry].keys()
                ):
                    processed_object["parserInfo"]["runningBuilds"][job_to_retry][build] = ""

            finished_builds = helpers.get_finished_builds(job_dir, total_running_builds)

            # Parse logs of finished builds
            if finished_builds:
                print(
                    "["
                    + job_to_retry
                    + "] Builds #"
                    + str(", #".join(finished_builds))
                    + " have already finished. Processing ..."
                )
                for build in sorted(finished_builds):
                    process_build(
                        build,
                        job_dir,
                        job_to_retry,
                        error_list,
                        retry_object,
                        retry_delay,
                    )
                    processed_object["parserInfo"]["runningBuilds"][job_to_retry].pop(build)
                # Update last processed log only if greater than current revision number
                max_latest_revision = max([int(build_id) for build_id in finished_builds])
                if max_latest_revision > int(latest_revision):
                    processed_object["parserInfo"]["lastRevision"][
                        job_to_retry
                    ] = max_latest_revision

            # Get updated value for total_running_builds
            total_running_builds = list(
                processed_object["parserInfo"]["runningBuilds"][job_to_retry].keys()
            )

            if total_running_builds and time_check == True:
                print(
                    "["
                    + job_to_retry
                    + "] Builds #"
                    + str(", #".join(total_running_builds))
                    + " are still running for job "
                    + job_to_retry
                )
                for build_to_check in sorted(total_running_builds):
                    check_running_time(job_dir, build_to_check, job_to_retry, max_running_time)

            # print("[" + job_to_retry + "] ... Done")

        # Check for delayed retries
        if retry_entries:
            for entry in list(retry_entries):
                if (
                    datetime.datetime.strptime(
                        retry_entries[entry]["retryTime"], "%Y-%m-%d %H:%M:%S"
                    )
                    < datetime.datetime.now()
                ):
                    print("Triggering delayed retry for " + entry)
                    trigger_retry = retry_entries[entry]["retryCommand"]
                    print(trigger_retry)
                    os.system(trigger_retry)
                    retry_object["retryQueue"].pop(entry)

            # Reset copy
            retry_entries = retry_object["retryQueue"]
            with open(retry_queue_path, "w") as retry_file:
                json.dump(retry_object, retry_file, indent=2)

        # Enable time check and delayed retries every 10 min
        if elapsed_time / (datetime.timedelta(minutes=10) * T) > 1:
            time_check = True
            T += 1
        else:
            time_check = False

        with open(parser_info_path, "w") as processed_file:
            json.dump(processed_object, processed_file, indent=2)

        if elapsed_time > datetime.timedelta(hours=2):
            break

        # print("[Parser information updated]")
        # Trigger cmssdt page update
        actions.update_cmssdt_page(html_file_path, "", "", "", "", "", "", True)
        time.sleep(2)
