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


def check_and_trigger_action(build_to_retry, job_dir, job_to_retry, error_list_action):
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

    job_url = (
        os.environ.get("JENKINS_URL") + "job/" + job_to_retry + "/" + build_to_retry
    )

    print("Parsing build #" + build_to_retry + " (" + job_url + ") ...")

    regex_flag = 0
    for error_and_action in error_list:
        regex_and_action = error_and_action.split(" - ")
        regex = regex_and_action[0]
        action = regex_and_action[1]
        for line in reversed(lines):
            if re.search(regex, line):
                print(
                    "... Found message "
                    + regex
                    + " in "
                    + log_file_path
                    + ". Taking action ..."
                )
                if action == "retryBuild":
                    actions.trigger_retry_action(
                        job_to_retry,
                        job_url,
                        build_to_retry,
                        build_dir_path,
                        action,
                        regex,
                        force_retry_regex,
                    )
                else:
                    # Take action on the nodes
                    node_name = (
                        helpers.grep(envvars_file_path, "NODE_NAME=", True)
                        .split("=")[1]
                        .replace("\n", "")
                    )
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
                        actions.trigger_nodeoff_action(
                            job_to_retry, build_to_retry, job_url, node_name
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
                        actions.notify_nodeoff(
                            node_name,
                            regex,
                            job_to_retry,
                            build_to_retry,
                            job_url,
                            node_url,
                            parser_url,
                        )
                    elif action == "nodeReconnect":
                        actions.trigger_reconnect_action(
                            job_to_retry, build_to_retry, job_url, node_name
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
                        actions.notify_nodereconnect(
                            node_name,
                            regex,
                            job_to_retry,
                            build_to_retry,
                            job_url,
                            node_url,
                            parser_url,
                        )

                regex_flag = 1
                break
            if regex_flag == 1:
                break
        if regex_flag == 1:
            break

    # Mark as retried
    actions.mark_build_as_retried(job_dir, job_to_retry, build_to_retry)
    with open(parser_info_path, "w") as processed_file:
        json.dump(processed_object, processed_file, indent=2)

    if regex_flag == 0:
        print("... no known errors were found.")
        if helpers.grep(os.path.join(build_dir_path, "build.xml"), "<result>FAILURE"):
            # Update description to inform that no action has been taken
            actions.update_no_action_label(job_to_retry, build_to_retry)
            actions.update_cmssdt_page(
                html_file_path,
                job_to_retry,
                build_to_retry,
                "No error found. Please, take the appropiate action",
                job_url,
                "[ No action taken ]",
                "NoAction",
            )


def check_running_time(job_dir, build_to_retry, job_to_retry, max_running_time=18):
    """Check builds running time and notify in case it exceeds the maximum time defined (default max time = 18h)."""
    job_url = (
        os.environ.get("JENKINS_URL") + "job/" + job_to_retry + "/" + build_to_retry
    )
    parser_url = (
        os.environ.get("JENKINS_URL") + "job/jenkins-test-parser/" + parser_build_id
    )

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

    build_file_path = functools.reduce(
        os.path.join, [job_dir, build_to_check, "build.xml"]
    )

    if not os.path.exists(build_file_path):
        return

    start_timestamp = (
        helpers.grep(build_file_path, "<startTime>", True)
        .replace("<startTime>", "")
        .replace("</startTime>", "")
    )

    display_name = (
        helpers.grep(build_file_path, "<displayName>", True)
        .replace("<displayName>", "")
        .replace("</displayName>", "")
        .replace("\n", "")
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

        processed_object["parserInfo"]["runningBuilds"][job_to_retry][
            build_to_retry
        ] = "emailSent"

        # Mark as notified
        actions.notify_pendingbuild(
            display_name, build_to_retry, job_to_retry, duration, job_url, parser_url,
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


def first_iter_check(job_to_retry, job_dir, error_list, processed_object):
    print("Checking first run for", job_to_retry)
    # Check if some builds have finished in the mean time
    try:
        last_processed_log = processed_object["parserInfo"]["lastRevision"][
            job_to_retry
        ]
    except KeyError:
        # If last processed log not defined, all logs will be parsed
        last_processed_log = 1
        processed_object["parserInfo"]["lastRevision"][
            job_to_retry
        ] = last_processed_log

    print(" ---> Last processed log: ", last_processed_log)

    finished_builds = [
        dir.name
        for dir in os.scandir(job_dir)
        if dir.name.isdigit()
        and int(dir.name) > int(last_processed_log)
        and os.path.isfile(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"])
        )
        and helpers.grep(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"]), "<result>"
        )
    ]

    if finished_builds:
        print(
            "Builds " + str(finished_builds) + " have already finished. Processing ..."
        )
        for build in sorted(finished_builds):
            check_and_trigger_action(build, job_dir, job_to_retry, error_list)
            # Cleaning bellow -->
        processed_object["parserInfo"]["lastRevision"][job_to_retry] = max(
            finished_builds
        )

    # If a build has finished, remove it from tracking
    try:
        running_builds = processed_object["parserInfo"]["runningBuilds"][
            job_to_retry
        ].keys()
    except KeyError:
        processed_object["parserInfo"]["runningBuilds"][job_to_retry] = dict()
        running_builds = []

    # --> Clean object from already parsed builds:
    for build in list(running_builds):
        if build in finished_builds:
            processed_object["parserInfo"]["runningBuilds"][job_to_retry].pop(build)

    return [build for build in running_builds if build not in finished_builds]


if __name__ == "__main__":

    # Set start time
    start_time = datetime.datetime.now()

    # Parse the build id of the current job
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "parser_build_id", help="Input current build id from Jenkins env vars"
    )
    args = parser.parse_args()
    parser_build_id = args.parser_build_id

    # Define paths:
    jobs_config_path = "cms-bot/jenkins/parser/jobs-config.json"  # This file matches job with their known errors and the action to perform
    builds_dir = os.environ.get("HOME") + "/builds"  # Path to the actual build logs
    parser_info_path = (
        os.environ.get("HOME") + "/builds/jenkins-test-parser/parser-info.json"
    )  # This file keeps track of the last log processed and the pending builds
    html_file_path = (
        os.environ.get("HOME")
        + "/builds/jenkins-test-parser-monitor/json-web-info.json"
    )

    # Get job-config info
    with open(jobs_config_path, "r") as jobs_file:
        jobs_object = json.load(jobs_file)
        jenkins_jobs = jobs_object["jobsConfig"]["jenkinsJobs"]

    # Get parser-info from previous run
    with open(
        parser_info_path, "r"
    ) as processed_file:  # Get last parsed object just once
        processed_object = json.load(processed_file)

    first_iter = True

    while True:
        current_time = datetime.datetime.now()
        elapsed_time = current_time - start_time

        # Iterate over all the jobs jobs_object["jobsConfig"]["jenkinsJobs"][ii]["jobName"]
        for job_id in range(len(jenkins_jobs)):
            job_to_retry = jenkins_jobs[job_id]["jobName"]
            try:
                max_running_time = int(jenkins_jobs[job_id]["maxTime"])
            except KeyError:
                # The default max running time is 18h for all builds
                max_running_time = 18

            print("[" + job_to_retry + "] Processing ...")
            job_dir = os.path.join(builds_dir, job_to_retry)
            error_list, force_retry_regex = helpers.get_errors_list(jobs_object, job_id)

            # If first run, we make sure we are not missing any finished build from previous run
            if first_iter == True:
                running_builds = first_iter_check(
                    job_to_retry, job_dir, error_list, processed_object
                )

            try:
                running_builds = processed_object["parserInfo"]["runningBuilds"][
                    job_to_retry
                ].keys()
            except KeyError:
                processed_object["parserInfo"]["runningBuilds"][job_to_retry] = dict()
                running_builds = []

            finished_builds = helpers.get_finished_builds(job_dir, running_builds)
            running_builds = helpers.get_running_builds(job_dir)

            # Update running builds in the original object
            for build in running_builds:
                if (
                    build
                    not in processed_object["parserInfo"]["runningBuilds"][
                        job_to_retry
                    ].keys()
                ):
                    processed_object["parserInfo"]["runningBuilds"][job_to_retry][
                        build
                    ] = ""

            # Parse logs of finished builds
            if finished_builds:
                print(
                    "Builds "
                    + str(finished_builds)
                    + " have already finished. Processing ..."
                )
                for build in sorted(finished_builds):
                    check_and_trigger_action(build, job_dir, job_to_retry, error_list)
                    # Pop build number from the tracking
                    processed_object["parserInfo"]["runningBuilds"][job_to_retry].pop(
                        build
                    )
                # Update last processed log
                # TODO: Only update if greater than current revision number
                processed_object["parserInfo"]["lastRevision"][job_to_retry] = max(
                    finished_builds
                )

            if running_builds:
                print(
                    "Builds "
                    + str(running_builds)
                    + " are still running for job "
                    + job_to_retry
                )
                for build_to_check in sorted(running_builds):
                    check_running_time(
                        job_dir, build_to_check, job_to_retry, max_running_time
                    )

        first_iter = False
        with open(parser_info_path, "w") as processed_file:
            json.dump(processed_object, processed_file, indent=2)

        if elapsed_time > datetime.timedelta(hours=2):
            # Save last parsed log and current running builds in file
            # TODO: Not necessary to save here
            with open(parser_info_path, "w") as processed_file:
                json.dump(processed_object, processed_file, indent=2)
            break

        print("[Parser information updated]")
        # Trigger cmssdt page update
        actions.update_cmssdt_page(html_file_path, "", "", "", "", "", "", True)
        time.sleep(20)
