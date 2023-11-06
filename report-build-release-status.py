#!/usr/bin/env python

from __future__ import print_function
from _py2with3compatibility import getoutput
from optparse import OptionParser
from github_utils import (
    create_issue_comment,
    get_issue_labels,
    remove_issue_label,
    add_issue_labels,
    remove_issue_labels_all,
)
from os.path import expanduser
from datetime import datetime
from socket import setdefaulttimeout
from os import environ
import re

setdefaulttimeout(120)
JENKINS_PREFIX = "jenkins"
try:
    JENKINS_PREFIX = environ["JENKINS_URL"].strip("/").split("/")[-1]
except:
    JENKINS_PREFIX = "jenkins"
#
# Posts a message in the github issue that triggered the build
# The structure of the message depends on the option used
#

# -------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------
GH_CMSSW_ORGANIZATION = "cms-sw"
GH_CMSSW_REPO = "cmssw"
POST_BUILDING = "BUILDING"
POST_TOOL_CONF_BUILDING = "TOOL_CONF_BUILDING"
BUILD_OK = "BUILD_OK"
TOOL_CONF_OK = "TOOL_CONF_OK"
TOOL_CONF_ERROR = "TOOL_CONF_ERROR"
BUILD_ERROR = "BUILD_ERROR"
UPLOADING = "UPLOADING"
UPLOAD_OK = "UPLOAD_OK"
UPLOAD_ERROR = "UPLOAD_ERROR"
CLEANUP_OK = "CLEANUP_OK"
CLEANUP_ERROR = "CLEANUP_ERROR"
TESTS_OK = "TESTS_OK"
RELEASE_NOTES_OK = "RELEASE_NOTES_OK"
RELEASE_NOTES_ERROR = "RELEASE_NOTES_ERROR"
INSTALLATION_OK = "INSTALLATION_OK"
INSTALLATION_SKIP = "INSTALLATION_SKIP"
INSTALLATION_ERROR = "INSTALLATION_ERROR"
# this means that there was an error in the script that excecutes the tests,
# it is independent from the tests results
TESTS_ERROR = "TESTS_ERROR"
BUILDING_MSG = (
    "The build has started for {architecture} in {machine}. \n"
    "You can see the progress here: https://cmssdt.cern.ch/%s/job/build-release/{jk_build_number}/console \n"
    "{details}" % JENKINS_PREFIX
)
BUILDING_TOOL_CONF_MSG = (
    "The cmssw-tool-conf build has started for {architecture} in {machine}. \n"
    "You can see the progress here: https://cmssdt.cern.ch/%s/job/build-release/{jk_build_number}/console \n"
    "{details}" % JENKINS_PREFIX
)
BUILD_OK_MSG = (
    "The build has finished sucessfully for the architecture {architecture} and is ready to be uploaded. \n"
    'You can start the uploads by writing the comment: "upload all". I will upload all the architectures as soon as the build finishes successfully.\n'
    "You can see the log for the build here: \n"
    "{log_url} \n"
    "Some tests ( runTheMatrix.py -s ) are being run, the results will be posted when done."
)
TOOL_CONF_OK_MSG = (
    "The cmssw-tool-conf build has finished sucessfully for the architecture {architecture} and it was automatically uploaded. \n"
    'Remember that if you write "+1" I will start to build this and all the architectures as soon as their cmssw-tool-conf finish.\n'
    "You can see the log for the build here: \n"
    "{log_url} \n"
)
TOOL_CONF_ERROR_MSG = (
    "There was an error building cmssw-tool-conf for {architecture} \n"
    "You can see the log for the build here: \n"
    "{log_url} \n"
)
UPLOADING_MSG = (
    "The upload has started for {architecture} in {machine}. \n"
    "You can see the progress here: https://cmssdt.cern.ch/%s/job/upload-release/{jk_build_number}/console"
    % JENKINS_PREFIX
)
UPLOAD_OK_MSG = "The upload has successfully finished for {architecture} \n You can see the log here: \n {log_url}"
INSTALLATION_OK_MSG = (
    "The installation has successfully finished for {architecture} \n You can see the log here: \n {log_url} \n"
    'To generate the release notes for the release write "release-notes since \\<previous-release\\>", in the first line of your comment.\n '
    "I will generate the release notes based on the release that you provide. You don't need to provide the architecture "
    "I will use the production architecture to infer the cmsdist tag.\n"
    'Alternatively, you can just write "release-notes", I will try to guess the previous release.'
)
INSTALLATION_SKIP_MSG = (
    "CERN AFS installation skipped for {architecture} as no CMSSW releases are now deployed on AFS. \n"
    'To generate the release notes for the release write "release-notes since \\<previous-release\\>", in the first line of your comment.\n '
    "I will generate the release notes based on the release that you provide. You don't need to provide the architecture "
    "I will use the production architecture to infer the cmsdist tag.\n"
    'Alternatively, you can just write "release-notes", I will try to guess the previous release.'
)
UPLOAD_ERROR_MSG = (
    "The was error uploading {architecture}. \n You can see the log here: \n {log_url}"
)
INSTALLATION_ERROR_MSG = (
    "The was error installing {architecture}. \n You can see the log here: \n {log_url}"
)
CLEANUP_OK_MSG = "The workspace for {architecture} has been deleted \n You can see the log here: \n {log_url} \n"
CLEANUP_ERROR_MSG = "There was an error deletng the workspace for {architecture} \n You can see the log here: \n {log_url} \n"
TESTS_OK_MSG = (
    "The tests have finished for {architecture} \n You can see the log here: \n {log_url} \n"
)
TESTS_ERROR_MSG = "There was an error when running the tests for {architecture} \n You can see the log here: \n {log_url} \n"
BUILD_ERROR_MSG = "The was an error for {architecture}. \n You can see the log here: \n {log_url}"
RELEASE_NOTES_OK_MSG = (
    "The release notes are ready: https://github.com/cms-sw/cmssw/releases/tag/{rel_name}"
)
RELEASE_NOTES_ERROR_MSG = (
    "There was an error generating the release notes, please look into the logs"
)
BUILD_QUEUED_LABEL = "build-release-queued"
BUILD_STARTED = "build-release-started"
BASE_BUILD_LOG_URL = (
    "https://cmssdt.cern.ch/SDT/" + JENKINS_PREFIX + "-artifacts/auto-build-release/%s-%s/%d"
)
BASE_UPLOAD_LOG_URL = (
    "https://cmssdt.cern.ch/SDT/" + JENKINS_PREFIX + "-artifacts/auto-upload-release/%s-%s/%d"
)
BASE_CLEANUP_LOG_URL = (
    "https://cmssdt.cern.ch/SDT/" + JENKINS_PREFIX + "-artifacts/cleanup-auto-build/%s-%s/%d"
)
BASE_INSTALLATION_URL = (
    "https://cmssdt.cern.ch/SDT/%s-artifacts/deploy-release-afs/{rel_name}/{architecture}/{job_id}/"
    % JENKINS_PREFIX
)

# -------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------


#
# posts a message to the issue in github
# if dry-run is selected it doesn't post the message and just prints it
#
def post_message(repo, issue, msg):
    if opts.dryRun:
        print("Not posting message (dry-run):\n %s" % msg)
    else:
        print("Posting message:\n %s" % msg)
        create_issue_comment(repo, issue, msg)


# Adds a label to the issue in github
# if dry-run is selected it doesn't add the label and just prints it
def add_label(repo, issue, label):
    if opts.dryRun:
        print("Not adding label (dry-run):\n %s" % label)
        return
    print("Adding label:\n %s" % label)
    add_issue_labels(repo, issue, [label])


# Removes a label form the issue
def remove_label(repo, issue, label):
    if opts.dryRun:
        print("Not removing label (dry-run):\n %s" % label)
        return

    reM = re.compile("^%s$" % label)
    for l in ALL_LABELS:
        if not reM.match(l):
            continue
        print("Removing label: %s" % l)
        try:
            remove_issue_label(repo, issue, l)
        except Exception as e:
            pass


#
# removes the labels of the issue
#
def remove_labels(repo, issue):
    if opts.dryRun:
        print("Not removing issue labels (dry-run)")
        return
    remove_issue_labels_all(repo, issue)


#
# Get tests log output
#
def get_test_log(logfile):
    from os import getenv
    from os.path import join, exists

    logmsg = ""
    try:
        logfile = join(getenv("WORKSPACE"), logfile)
        try:
            logmsg = "\n\nTests results:\n" + getoutput("grep 'ERROR\| tests passed' " + logfile)
        except:
            logmsg = "\n\nUnable to read tests log: No such file " + logfile
    except:
        logmsg = "\n\nUnable to read tests log: WORKSPACE variable not set."
    return logmsg


# Start of execution
# --------------------------------------------------------------------------------

if __name__ == "__main__":
    parser = OptionParser(
        usage="%prog <jenkins-build-number> <hostname> <issue-id> <arch> <release-name> <message-type> [ options ] \n "
        "message-type = BUILDING | BUILD_OK | BUILD_ERROR | UPLOADING | UPLOAD_OK | UPLOAD_ERROR | CLEANUP_OK | CLEANUP_ERROR | TESTS_OK | TESTS_ERROR "
        "| RELEASE_NOTES_OK | RELEASE_NOTES_ERROR | INSTALLATION_OK | INSTALLATION_ERROR | INSTALLATION_SKIP"
    )
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not post on Github",
        default=False,
    )
    parser.add_option(
        "-d",
        "--details",
        dest="details",
        action="store",
        help="Add aditional details to the message",
        default=False,
    )

    opts, args = parser.parse_args()
    if len(args) != 6:
        parser.error("Not enough arguments")

    jenkins_build_number = int(args[0])
    hostname = args[1]
    issue = int(args[2])
    arch = args[3]
    release_name = args[4]
    action = args[5]

    repo = GH_CMSSW_ORGANIZATION + "/" + GH_CMSSW_REPO
    ALL_LABELS = [l["name"] for l in get_issue_labels(repo, issue)]
    test_logfile = "build/" + release_name + "-tests/matrixTests/runall-report-step123-.log"

    if action == POST_BUILDING:
        msg_details = ""
        if opts.details:
            msg_details = opts.details
        msg = BUILDING_MSG.format(
            architecture=arch,
            machine=hostname,
            jk_build_number=jenkins_build_number,
            details=msg_details,
        )
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        new_label = arch + "-building"
        add_label(repo, issue, new_label)

    elif action == POST_TOOL_CONF_BUILDING:
        msg_details = ""
        if opts.details:
            msg_details = opts.details
        msg = BUILDING_TOOL_CONF_MSG.format(
            architecture=arch,
            machine=hostname,
            jk_build_number=jenkins_build_number,
            details=msg_details,
        )
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        new_label = arch + "-tool-conf-building"
        add_label(repo, issue, new_label)

    elif action == BUILD_OK:
        results_url = BASE_BUILD_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = BUILD_OK_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        add_label(repo, issue, arch + "-build-ok")

    elif action == TOOL_CONF_OK:
        results_url = BASE_BUILD_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = TOOL_CONF_OK_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        add_label(repo, issue, arch + "-tool-conf-ok")

    elif action == BUILD_ERROR:
        results_url = BASE_BUILD_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = BUILD_ERROR_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        add_label(repo, issue, arch + "-build-error")

    elif action == TOOL_CONF_ERROR:
        results_url = BASE_BUILD_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = TOOL_CONF_ERROR_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        add_label(repo, issue, arch + "-tool-conf-error")

    elif action == UPLOADING:
        msg = UPLOADING_MSG.format(
            architecture=arch, machine=hostname, jk_build_number=jenkins_build_number
        )
        post_message(repo, issue, msg)

    elif action == UPLOAD_OK:
        results_url = BASE_UPLOAD_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = UPLOAD_OK_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        add_label(repo, issue, arch + "-upload-ok")

    elif action == UPLOAD_ERROR:
        results_url = BASE_UPLOAD_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = UPLOAD_ERROR_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        add_label(repo, issue, arch + "-upload-error")

    elif action == CLEANUP_OK:
        results_url = BASE_CLEANUP_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = CLEANUP_OK_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)

    elif action == CLEANUP_ERROR:
        results_url = BASE_CLEANUP_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = CLEANUP_ERROR_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)

    elif action == TESTS_OK:
        results_url = BASE_BUILD_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = TESTS_OK_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg + get_test_log(test_logfile))

    elif action == TESTS_ERROR:
        results_url = BASE_BUILD_LOG_URL % (release_name, arch, jenkins_build_number)
        msg = TESTS_ERROR_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg + get_test_log(test_logfile))

    elif action == RELEASE_NOTES_OK:
        msg = RELEASE_NOTES_OK_MSG.format(rel_name=release_name)
        post_message(repo, issue, msg)

    elif action == RELEASE_NOTES_ERROR:
        msg = RELEASE_NOTES_ERROR_MSG.format(rel_name=release_name)
        post_message(repo, issue, msg)

    elif action in [INSTALLATION_OK, INSTALLATION_SKIP]:
        results_url = BASE_INSTALLATION_URL.format(
            rel_name=release_name, architecture=arch, job_id=jenkins_build_number
        )
        # msg = INSTALLATION_OK_MSG.format( architecture=arch , log_url=results_url )
        # if action == INSTALLATION_SKIP:
        #  msg = INSTALLATION_SKIP_MSG.format( architecture=arch , log_url=results_url )
        # post_message( repo, issue, msg )
        remove_label(repo, issue, arch + "-.*")
        add_label(repo, issue, arch + "-installation-ok")

    elif action == INSTALLATION_ERROR:
        results_url = BASE_INSTALLATION_URL.format(
            rel_name=release_name, architecture=arch, job_id=jenkins_build_number
        )
        msg = INSTALLATION_ERROR_MSG.format(architecture=arch, log_url=results_url)
        post_message(repo, issue, msg)
        remove_label(repo, issue, arch + "-.*")
        add_label(repo, issue, arch + "-installation-error")

    else:
        parser.error("Message type not recognized")
