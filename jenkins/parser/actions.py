import functools
import os
import time
import json
import datetime

import helpers


email_addresses = "cms-sdt-logs@cern.ch"

html_file_path = os.environ.get("HOME") + "/builds/jenkins-test-parser-monitor/json-web-info.json"
retry_url_file = (
    os.environ.get("HOME") + "/builds/jenkins-test-parser-monitor/json-retry-info.json"
)
retry_queue_path = os.environ.get("HOME") + "/builds/jenkins-test-parser/retry_queue.json"


def send_email(email_msg, email_subject, email_addresses):
    email_cmd = 'echo "' + email_msg + '" | mail -s "' + email_subject + '" ' + email_addresses
    print(email_cmd)
    os.system(email_cmd)


def trigger_create_gridnode_action(node_name):
    node_config_path = os.environ.get("HOME") + "/nodes/" + node_name + "/config.xml"
    if helpers.grep(node_config_path, "auto-recreate", True):
        print("Recreating grid node ...")
        trigger_create_gridnode = os.environ.get("JENKINS_CLI_CMD") + " build grid-create-node"
        print(trigger_create_gridnode)
        os.system(trigger_create_gridnode)
    else:
        print("Skipping grid node recreation ...")


def trigger_retry_action(
    job_to_retry,
    job_url,
    build_to_retry,
    build_dir_path,
    action,
    regex,
    force_retry_regex,
    retry_object="",
    delay_time="",
):
    # Skip autoretry if Jenkins already retries, unless connection issue.
    if regex not in force_retry_regex:
        if helpers.grep(os.path.join(build_dir_path, "build.xml"), "<maxSchedule>", True):
            print("... Jenkins already takes care of retrying. Skipping ...")
            if helpers.grep(os.path.join(build_dir_path, "build.xml"), "<retryCount>", True):
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
        + ' -p ERROR="'
        + str(regex.replace(" ", "&"))
        + '"'
    )
    if action == "retryNow":
        print(trigger_retry)
        os.system(trigger_retry)
        update_cmssdt_page(
            html_file_path, job_to_retry, build_to_retry, regex, job_url, "", "Retry"
        )
    elif action == "retryLate":
        # Store retry command into a file
        print("This failure will be retried with a delay of " + str(delay_time) + " min")
        retry_entry = job_to_retry + "#" + build_to_retry
        retry_time = datetime.datetime.now().replace(microsecond=0) + datetime.timedelta(
            minutes=delay_time
        )
        retry_object["retryQueue"][retry_entry] = {}
        retry_object["retryQueue"][retry_entry]["retryTime"] = str(retry_time)
        retry_object["retryQueue"][retry_entry]["retryCommand"] = trigger_retry

        with open(retry_queue_path, "w") as retry_file:
            json.dump(retry_object, retry_file, indent=2)

        # Update description of the failed job
        update_label = (
            os.environ.get("JENKINS_CLI_CMD")
            + " set-build-description "
            + job_to_retry
            + " "
            + build_to_retry
            + " 'Build\ will\ be\ retried\ with\ some\ delay'"
        )
        print(update_label)
        os.system(update_label)
    else:
        print(trigger_retry)
        os.system(trigger_retry)


def trigger_nodeoff_action(job_to_retry, build_to_retry, job_url, node_name):
    nodeoff_msg = "'Node\ marked\ as\ offline\ beacuse\ of\ " + job_url + "'"
    take_nodeoff = (
        os.environ.get("JENKINS_CLI_CMD") + " offline-node " + node_name + " -m " + nodeoff_msg
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


def trigger_reconnect_action(job_to_retry, build_to_retry, job_url, node_name):
    nodeoff_msg = "'Node\ reconnected\ by\ " + job_url + "'"
    disconnect_node = (
        os.environ.get("JENKINS_CLI_CMD") + " disconnect-node " + node_name + " -m " + nodeoff_msg
    )
    connect_node = os.environ.get("JENKINS_CLI_CMD") + " connect-node " + node_name + " -f"
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


def notify_nodeoff(node_name, regex, job_to_retry, build_to_retry, job_url, node_url, parser_url):
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


def notify_pendingbuild(display_name, build_to_retry, job_to_retry, duration, job_url, parser_url):
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
        "Pending build " + display_name + " (#" + build_to_retry + ") from job " + job_to_retry
    )

    email_cmd = 'echo "' + email_msg + '" | mail -s "' + email_subject + '" ' + email_addresses
    send_email(email_msg, email_subject, email_addresses)


def mark_build_as_retried(job_dir, job_to_retry, build_to_retry):
    if helpers.grep(
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


def update_no_action_label(job_to_retry, build_to_retry, job_url):
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


def notify_noaction(display_name, job_to_retry, build_to_retry, job_url):
    email_msg = (
        "Build failed in job "
        + job_to_retry
        + ","
        + display_name
        + ".\nNo action has been taken by parser job. Please, take the appropiate action.\n\nFailed job: "
        + job_url
    )
    email_subject = "Build failed in Jenkins: " + job_to_retry + " " + display_name
    send_email(email_msg, email_subject, email_addresses)


def update_cmssdt_page(
    html_file, job, build, error, job_url, retry_url, action, refresh_only=False
):

    try:
        with open(html_file, "r") as openfile:
            json_object = json.load(openfile)
    except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
        # Handle file not found error or JSON decoding error
        print(f"Error occurred: {str(e)}")
        print("Restoring json-web-info.json file...")
        with open(html_file, "w") as json_file:
            json_object = {"parserActions": {}}
            json.dump(json_object, json_file)

    if refresh_only == False:

        id = str(job + "#" + build)
        retry_time = datetime.datetime.now().replace(microsecond=0)

        json_object["parserActions"][id] = dict()
        json_object["parserActions"][id]["actionTime"] = str(retry_time)
        json_object["parserActions"][id]["jobName"] = job
        json_object["parserActions"][id]["buildNumber"] = build
        json_object["parserActions"][id]["errorMsg"] = error
        json_object["parserActions"][id]["failedBuild"] = job_url
        json_object["parserActions"][id]["retryJob"] = retry_url
        json_object["parserActions"][id]["parserAction"] = action

    json_object, cleanup_flag = cleanup_cmssdt_page(json_object)

    with open(html_file, "w") as openfile:
        json.dump(json_object, openfile, indent=2)

    trigger_web_update = os.environ.get("JENKINS_CLI_CMD") + " build jenkins-test-parser-monitor"

    if refresh_only == False or cleanup_flag == 1:

        print(trigger_web_update)
        os.system(trigger_web_update)


def cleanup_cmssdt_page(json_object):

    builds_dir = os.environ.get("HOME") + "/builds"
    cleanup_flag = 0

    # [CLEANUP]: Loop over the entries to clean up static page
    for entry in list(json_object["parserActions"].keys()):
        job_to_retry = json_object["parserActions"][entry]["jobName"]
        build_to_retry = json_object["parserActions"][entry]["buildNumber"]
        action_time = json_object["parserActions"][entry]["actionTime"]
        action_type = json_object["parserActions"][entry]["parserAction"]

        # [CLEANUP 1]: If job has been removed from Jenkins
        job_dir = os.path.join(builds_dir, job_to_retry)
        if not os.path.exists(os.path.join(job_dir, build_to_retry)):
            json_object["parserActions"].pop(entry)
            print(
                "[CLEANUP 1] Removing monitor entry for job "
                + job_to_retry
                + " #"
                + build_to_retry
            )
            cleanup_flag = 1
            continue

        # [CLEANUP 2]: Remove entries older than 2 days
        current_time = datetime.datetime.now().replace(microsecond=0)
        if current_time > datetime.datetime.strptime(
            action_time, "%Y-%m-%d %H:%M:%S"
        ) + datetime.timedelta(days=2):
            json_object["parserActions"].pop(entry)
            print(
                "[CLEANUP 2] Removing monitor entry for job "
                + job_to_retry
                + " #"
                + build_to_retry
            )
            cleanup_flag = 1
            continue

        # [CLEANUP 3]: Remove entry if external action has taken
        if action_type == "NoAction" and not helpers.grep(
            functools.reduce(os.path.join, [job_dir, build_to_retry, "build.xml"]),
            "No action has been taken by the parser job",
            True,
        ):
            json_object["parserActions"].pop(entry)
            print(
                "[CLEANUP 3] Removing monitor entry for job "
                + job_to_retry
                + " #"
                + build_to_retry
            )
            cleanup_flag = 1

    return json_object, cleanup_flag


def update_retry_link_cmssdt_page(retry_url_file, job, build, retry_url):

    with open(retry_url_file, "r") as openfile:
        json_object = json.load(openfile)

    if job in json_object["retryUrl"].keys():
        json_object["retryUrl"][job][build] = retry_url
    else:
        json_object["retryUrl"][job] = dict()
        json_object["retryUrl"][job][build] = retry_url

    with open(retry_url_file, "w") as openfile:
        json.dump(json_object, openfile, indent=2)
