import functools
import os
import time

import helpers


email_addresses = "cms-sdt-logs@cern.ch"


def send_email(email_msg, email_subject, email_addresses):
    email_cmd = (
        'echo "' + email_msg + '" | mail -s "' + email_subject + '" ' + email_addresses
    )
    print(email_cmd)
    os.system(email_cmd)


def trigger_retry_action(
    job_to_retry, build_to_retry, build_dir_path, action, regex, force_retry_regex
):
    # Skip autoretry if Jenkins already retries, unless connection issue.
    if regex not in force_retry_regex:
        if helpers.grep(
            os.path.join(build_dir_path, "build.xml"), "<maxSchedule>", True
        ):
            print("... Jenkins already takes care of retrying. Skipping ...")
            if helpers.grep(
                os.path.join(build_dir_path, "build.xml"), "<retryCount>", True
            ):
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


def trigger_reconnect_action(job_to_retry, build_to_retry, job_url, node_name):
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


def update_no_action_label(job_to_retry, build_to_retry):
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
