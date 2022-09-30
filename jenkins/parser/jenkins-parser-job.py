#!/usr/bin/env python3

import argparse
import datetime
import functools
import json
import os
import re
import time


def grep(filename, pattern, verbose=False):
    """Bash-like grep function. Set verbose=True to print the line match."""
    with open(filename, "r") as file:
        for line in file:
            if re.search(pattern, line):
                if verbose:
                    return line
                else:
                    return True


def get_errors_list(jobs_object, job_id):
    """Get list of errors to check for a concrete job with the corresponding action."""

    # Get errorMsg object
    jenkins_errors = jobs_object["jobsConfig"]["errorMsg"]
    # Get common error messages and regex that must be force retried
    common_keys = []
    force_retry_regex = []
    for ii in jobs_object["jobsConfig"]["errorMsg"].keys():
        if jobs_object["jobsConfig"]["errorMsg"][ii]["allJobs"] == "true":
            common_keys.append(ii)
        if jobs_object["jobsConfig"]["errorMsg"][ii]["forceRetry"] == "true":
            force_retry_regex.extend(
                jobs_object["jobsConfig"]["errorMsg"][ii]["errorStr"]
            )
    # Get the error keys of the concrete job ii
    error_keys = jobs_object["jobsConfig"]["jenkinsJobs"][job_id]["errorType"][:]
    error_keys.extend(common_keys)
    error_keys = list(set(error_keys))

    # Get the error messages of the error keys
    error_list = []
    # We append the action to perform to the error message
    for ii in error_keys:
        if jenkins_errors[ii]["action"] == "retryBuild":
            for error in jenkins_errors[ii]["errorStr"]:
                error_list.append(error + " - retryBuild")
        elif jenkins_errors[ii]["action"] == "nodeOff":
            for error in jenkins_errors[ii]["errorStr"]:
                error_list.append(error + " - nodeOff")
        elif jenkins_errors[ii]["action"] == "nodeReconnect":
            for error in jenkins_errors[ii]["errorStr"]:
                error_list.append(error + " - nodeReconnect")
        else:
            print(
                "Action not defined. Please define a valid action in "
                + jobs_config_path
            )
    return error_list, force_retry_regex


def get_finished_builds(job_dir, last_processed_log):
    """Get list of finished builds for a concrete job.
       A build is finished if there is the <results> keyword in build.xml.
       Some sanity checks are also performed."""
    return [
        dir.name
        for dir in os.scandir(job_dir)
        if dir.name.isdigit()
        and int(dir.name) > int(last_processed_log)
        and os.path.isfile(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"])
        )
        and grep(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"]),
            "<result>",
        )
    ]


def get_pending_builds(
    job_dir, job_to_retry, last_processed_log, parser_info_path, running_builds
):
    """Get list of long running builds that are left behind in the trend list.
       Report the value from the last run and update it."""
    pending_builds = [
        dir.name
        for dir in os.scandir(job_dir)
        if dir.name.isdigit()
        and int(dir.name) <= int(last_processed_log)
        and os.path.isfile(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"])
        )
        and not grep(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"]), "<result>"
        )
    ]

    # We first check for the old running builds of last run
    with open(parser_info_path, "r") as rotation_file:
        last_pending_builds_object = json.load(rotation_file)
        last_pending_builds_dict = last_pending_builds_object["parserInfo"][
            "runningBuilds"
        ]

    if job_to_retry not in last_pending_builds_dict:
        last_pending_builds_dict[job_to_retry] = dict()
        last_pending_builds = dict()
    else:
        last_pending_builds = last_pending_builds_dict[job_to_retry]

    # Remove new running builds from list of old builds:
    last_pending_builds = list(set(last_pending_builds.keys()) - set(running_builds))

    # Update value of old running builds in the original object to store it again
    for build_number in pending_builds:
        if (
            build_number
            not in last_pending_builds_object["parserInfo"]["runningBuilds"][
                job_to_retry
            ].keys()
        ):
            last_pending_builds_object["parserInfo"]["runningBuilds"][job_to_retry][
                build_number
            ] = ""

    with open(parser_info_path, "w") as rotation_file:
        json.dump(last_pending_builds_object, rotation_file)

    return pending_builds, last_pending_builds


def get_running_builds(job_dir, last_processed_log):
    """Get list of new running builds that have been started after the last processed log."""
    return [
        dir.name
        for dir in os.scandir(job_dir)
        if dir.name.isdigit()
        and int(dir.name) > int(last_processed_log)
        and os.path.isfile(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"])
        )
        and not grep(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"]), "<result>"
        )
    ]


def trigger_retry_action(
    job_to_retry, build_to_retry, build_dir_path, action, regex, force_retry_regex
):
    # Skip autoretry if Jenkins already retries, unless connection issue.
    if regex not in force_retry_regex:
        if grep(os.path.join(build_dir_path, "build.xml"), "<maxSchedule>", True):
            print("... Jenkins already takes care of retrying. Skipping ...")
            if grep(os.path.join(build_dir_path, "build.xml"), "<retryCount>", True):
                return
            # Update description of the failed job
            update_label = (
                os.environ.get("JENKINS_CLI_CMD")
                + " set-build-description "
                + job_to_retry
                + " "
                + build_to_retry
                + " 'Retried\ by\ Jenkins'"
            )
            print(update_label)
            os.system(update_label)
            return

    trigger_retry = (
        os.environ.get("JENKINS_CLI_CMD")
        + " build jenkins-test-retry -p JOB_TO_RETRY="
        + job_to_retry
        + " -p BUILD_TO_RETRY="
        + build_to_retry
        + " -p ACTION="
        + action
    )
    print(trigger_retry)
    os.system(trigger_retry)


def trigger_nodeoff_action(job_to_retry, build_to_retry, job_url, node_name):
    nodeoff_msg = "'Node\ marked\ as\ offline\ beacuse\ of\ " + job_url + "'"
    take_nodeoff = (
        os.environ.get("JENKINS_CLI_CMD")
        + " offline-node "
        + node_name
        + " -m "
        + nodeoff_msg
    )
    print(take_nodeoff)
    os.system(take_nodeoff)

    # Update description of the failed job
    update_label = (
        os.environ.get("JENKINS_CLI_CMD")
        + " set-build-description "
        + job_to_retry
        + " "
        + build_to_retry
        + " 'Node\ marked\ as\ offline\ and\ job\ retried.\ Please,\ take\ the\ appropiate\ action\ and\ relaunch\ the\ node.\ Also,\ make\ sure\ that\ the\ job\ is\ running\ fine\ now.\ It\ might\ be\ queueing.'"
    )
    print(update_label)
    os.system(update_label)


def trigger_reconnect_action(job_ro_retry, build_to_retry, job_url, node_name):
    nodeoff_msg = "'Node\ reconnected\ by\ " + job_url + "'"
    disconnect_node = (
        os.environ.get("JENKINS_CLI_CMD")
        + " disconnect-node "
        + node_name
        + " -m "
        + nodeoff_msg
    )
    connect_node = (
        os.environ.get("JENKINS_CLI_CMD") + " connect-node " + node_name + " -f"
    )
    print(disconnect_node)
    os.system(disconnect_node)
    time.sleep(10)
    print(connect_node)
    os.system(connect_node)

    # Update description of the failed job
    update_label = (
        os.environ.get("JENKINS_CLI_CMD")
        + " set-build-description "
        + job_to_retry
        + " "
        + build_to_retry
        + " 'Node\ has\ been\ forced\ to\ reconnect\ and\ job\ has\ been\ retried.\ Please,\ make\ sure\ that\ the\ node\ is\ in\ good\ state\ and job\ is\ running\ fine\ now.\ It\ might\ be\ queueing.'"
    )
    print(update_label)
    os.system(update_label)


def send_email(email_msg, email_subject, email_addresses):
    email_cmd = (
        'echo "' + email_msg + '" | mail -s "' + email_subject + '" ' + email_addresses
    )
    print(email_cmd)
    os.system(email_cmd)


def notify_nodeoff(
    node_name, regex, job_to_retry, build_to_retry, job_url, node_url, parser_url
):
    email_msg = (
        "Node "
        + node_name
        + " has been disconnected because of an error of type <"
        + regex
        + "> in job "
        + job_to_retry
        + " build number "
        + build_to_retry
        + ".\nPlease, take the appropiate action.\n\nFailed job: "
        + job_url
        + "\n\nDisconnected node: "
        + node_url
        + "\n\nParser job: "
        + parser_url
    )
    email_subject = "Node " + node_name + " disconnected by jenkins-test-parser job"
    send_email(email_msg, email_subject, email_addresses)


def notify_nodereconnect(
    node_name, regex, job_to_retry, build_to_retry, job_url, node_url, parser_url
):
    email_msg = (
        "Node "
        + node_name
        + " has been forced to reconnect because of an error of type <"
        + regex
        + "> in job "
        + job_to_retry
        + " build number "
        + build_to_retry
        + ".\nPlease, take the appropiate action.\n\nFailed job: "
        + job_url
        + "\n\nAffected node: "
        + node_url
        + "\n\nParser job: "
        + parser_url
    )
    email_subject = "Node " + node_name + " reconnected by jenkins-test-parser job"
    send_email(email_msg, email_subject, email_addresses)


def notify_pendingbuild(
    display_name, build_to_retry, job_to_retry, duration, job_url, parser_url
):
    email_msg = (
        "Build"
        + display_name
        + " (#"
        + build_to_retry
        + ") from job "
        + job_to_retry
        + " has been running for an unexpected amount of time.\nTotal running time: "
        + str(duration)
        + ".\nPlease, take the appropiate action.\n\nPending job: "
        + job_url
        + "\n\nParser job: "
        + parser_url
    )

    email_subject = (
        "Pending build "
        + display_name
        + " (#"
        + build_to_retry
        + ") from job "
        + job_to_retry
    )

    email_cmd = (
        'echo "' + email_msg + '" | mail -s "' + email_subject + '" ' + email_addresses
    )
    send_email(email_msg, email_subject, email_addresses)


def check_and_trigger_action(build_to_retry, job_dir, job_to_retry, error_list_action):
    """Check failed build logs and trigger the appropiate action if a known error is found."""
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
                    trigger_retry_action(
                        job_to_retry,
                        build_to_retry,
                        build_dir_path,
                        action,
                        regex,
                        force_retry_regex,
                    )
                else:
                    # Take action on the nodes
                    node_name = (
                        grep(envvars_file_path, "NODE_NAME=", True)
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
                        trigger_nodeoff_action(
                            job_to_retry, build_to_retry, job_url, node_name
                        )
                        trigger_retry_action(
                            job_to_retry,
                            build_to_retry,
                            build_dir_path,
                            action,
                            regex,
                            force_retry_regex,
                        )
                        notify_nodeoff(
                            node_name,
                            regex,
                            job_to_retry,
                            build_to_retry,
                            job_url,
                            node_url,
                            parser_url,
                        )
                    elif action == "nodeReconnect":
                        trigger_reconnect_action(
                            job_ro_retry, build_to_retry, job_url, node_name
                        )
                        trigger_retry_action(
                            job_to_retry,
                            build_to_retry,
                            build_dir_path,
                            action,
                            regex,
                            force_retry_regex,
                        )
                        notify_nodereconnect(
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
    if regex_flag == 0:
        print("... no known errors were found.")

        if grep(os.path.join(build_dir_path, "build.xml"), "<result>FAILURE"):
            # Update description to inform that no action has been taken
            update_label = (
                os.environ.get("JENKINS_CLI_CMD")
                + " set-build-description "
                + job_to_retry
                + " "
                + build_to_retry
                + " '[No\ action\ has\ been\ taken\ by\ the\ parser\ job]'"
            )

            print(update_label)
            os.system(update_label)


def get_last_processed_log(parser_info_path, job_to_retry):
    """Get value of the last processed log from the workspace."""
    with open(parser_info_path, "r") as processed_file:
        processed_object = json.load(processed_file)
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

    return last_processed_log, processed_object


def update_last_processed_log(processed_object, job_to_retry, finished_builds):
    """Update build number value of the parser's last processed log."""
    processed_object["parserInfo"]["lastRevision"][job_to_retry] = max(finished_builds)

    with open(parser_info_path, "w") as processed_file:
        json.dump(processed_object, processed_file)


def check_running_time(
    build_file_path, build_to_retry, job_to_retry, max_running_time=18
):
    """Check running time of a build and send a notification if it exceeds the 18h."""
    start_timestamp = (
        grep(build_file_path, "<startTime>", True)
        .replace("<startTime>", "")
        .replace("</startTime>", "")
    )

    display_name = (
        grep(build_file_path, "<displayName>", True)
        .replace("<displayName>", "")
        .replace("</displayName>", "")
        .replace("\n", "")
    )

    start_datetime = datetime.datetime.fromtimestamp(int(start_timestamp) / 1000)
    now = datetime.datetime.now()
    duration = now - start_datetime

    job_url = (
        os.environ.get("JENKINS_URL") + "job/" + job_to_retry + "/" + build_to_retry
    )
    parser_url = (
        os.environ.get("JENKINS_URL") + "job/jenkins-test-parser/" + parser_build_id
    )

    with open(parser_info_path, "r") as rotation_file:
        last_pending_builds_object = json.load(rotation_file)

    if (
        build_to_retry
        not in last_pending_builds_object["parserInfo"]["runningBuilds"][job_to_retry]
    ):
        last_pending_builds_object["parserInfo"]["runningBuilds"][job_to_retry][
            build_to_retry
        ] = ""
        with open(parser_info_path, "w") as rotation_file:
            json.dump(last_pending_builds_object, rotation_file)

    if duration > datetime.timedelta(hours=max_running_time):

        if (
            last_pending_builds_object["parserInfo"]["runningBuilds"][job_to_retry][
                build_to_retry
            ]
            == ""
        ):
            print(
                "Build #"
                + build_to_retry
                + " ("
                + job_url
                + ") has been running for more than "
                + str(max_running_time)
                + " hours!"
            )

            notify_pendingbuild(
                display_name,
                build_to_retry,
                job_to_retry,
                duration,
                job_url,
                parser_url,
            )

            last_pending_builds_object["parserInfo"]["runningBuilds"][job_to_retry][
                build_to_retry
            ] = "emailSent"
            with open(parser_info_path, "w") as rotation_file:
                json.dump(last_pending_builds_object, rotation_file)
        else:
            print(
                "... Email notification already send for build #"
                + build_to_retry
                + " ("
                + job_url
                + "). It has been running for "
                + str(duration)
                + " hours ... Waiting for action"
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


def mark_build_as_retried(job_dir, job_to_retry, build_to_retry):
    if grep(
        functools.reduce(os.path.join, [job_dir, build_to_retry, "build.xml"]),
        "jenkins-test-retry",
        verbose=False,
    ):
        label = "Retried'\ 'build"

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


if __name__ == "__main__":

    # Parsing the build id of the current job
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "parser_build_id", help="Input current build id from Jenkins env vars"
    )
    args = parser.parse_args()
    parser_build_id = args.parser_build_id

    # Define paths:
    jobs_config_path = "cms-bot/jenkins/parser/jobs-config.json"  # This file matches job with their known errors and the action to perform
    parser_info_path = (
        os.environ.get("HOME") + "/builds/jenkins-test-parser/parser-info.json"
    )  # This file keeps track of the last log processed and the pending builds
    builds_dir = os.environ.get("HOME") + "/builds"  # Path to the actual build logs

    # Define e-mails to notify
    email_addresses = "cms-sdt-logs@cern.ch"

    with open(jobs_config_path, "r") as jobs_file:
        jobs_object = json.load(jobs_file)
        jenkins_jobs = jobs_object["jobsConfig"]["jenkinsJobs"]

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

            error_list, force_retry_regex = get_errors_list(jobs_object, job_id)

            last_processed_log, processed_object = get_last_processed_log(
                parser_info_path, job_to_retry
            )

            finished_builds = get_finished_builds(job_dir, last_processed_log)
            running_builds = get_running_builds(job_dir, last_processed_log)

            # Check for running builds left behind and store them to keep track
            pending_builds, last_pending_builds = get_pending_builds(
                job_dir,
                job_to_retry,
                last_processed_log,
                parser_info_path,
                running_builds,
            )

            if pending_builds or running_builds:
                print(
                    "Builds "
                    + str(pending_builds + running_builds)
                    + " are still running for job "
                    + job_to_retry
                )

            if not last_pending_builds and not running_builds:
                print("No builds running for " + job_to_retry)
                pass
            elif sorted(pending_builds) != sorted(last_pending_builds):
                extra_list = [
                    build
                    for build in last_pending_builds
                    if build not in pending_builds
                ]

                print(
                    "Builds "
                    + str(extra_list)
                    + " have already finished. Processing ..."
                )
                # Trigger the parsing in these builds
                for build_to_retry in extra_list:
                    check_and_trigger_action(
                        build_to_retry, job_dir, job_to_retry, error_list
                    )
                    # Remove from rotation dict
                    with open(parser_info_path, "r") as rotation_file:
                        last_pending_builds_object = json.load(rotation_file)

                    last_pending_builds_object["parserInfo"]["runningBuilds"][
                        job_to_retry
                    ].pop(build_to_retry)

                    with open(parser_info_path, "w") as rotation_file:
                        json.dump(last_pending_builds_object, rotation_file)
            else:
                print(
                    "Checking for how long the pending builds have been running (maximum running time: "
                    + str(max_running_time)
                    + " hours) ..."
                )
                for build_to_check in sorted(last_pending_builds + running_builds):
                    check_running_time(
                        functools.reduce(
                            os.path.join, [job_dir, build_to_check, "build.xml"]
                        ),
                        build_to_check,
                        job_to_retry,
                        max_running_time,
                    )

            if not finished_builds:
                print("No new finished builds for job " + job_to_retry + " to parse")
                continue

            print(
                "Job "
                + job_to_retry
                + " has the following new builds to process: "
                + str(finished_builds)
            )

            with open(parser_info_path, "r") as rotation_file:
                last_pending_builds_object = json.load(rotation_file)

            # Process logs of failed builds
            for build_to_retry in finished_builds:
                check_and_trigger_action(
                    build_to_retry, job_dir, job_to_retry, error_list
                )

                # Mark as retried
                mark_build_as_retried(job_dir, job_to_retry, build_to_retry)

            with open(parser_info_path, "w") as rotation_file:
                json.dump(last_pending_builds_object, rotation_file)

            # Update the value of the last log processed
            update_last_processed_log(processed_object, job_to_retry, finished_builds)

    print("All jobs have been checked!")
