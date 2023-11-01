#!/usr/bin/env python3
import json
import re
from _py2with3compatibility import run_cmd, quote, Request, urlopen, HTTPError
from datetime import datetime, timedelta
from optparse import OptionParser
from os.path import dirname, abspath, exists
from os.path import expanduser
from socket import setdefaulttimeout

import yaml

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from github import Github

from categories import REQUEST_BUILD_RELEASE, APPROVE_BUILD_RELEASE
from cms_static import BUILD_REL, GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, GH_CMSDIST_REPO
from cmsutils import get_config_map_properties, get_full_release_archs
from github_utils import api_rate_limits, get_ref_commit, get_commit_info
from github_utils import get_branch
from releases import get_release_managers

setdefaulttimeout(120)
from os import environ

JENKINS_PREFIX = "jenkins"
try:
    JENKINS_PREFIX = environ["JENKINS_URL"].strip("/").split("/")[-1]
except:
    JENKINS_PREFIX = "jenkins"

try:
    CMS_BOT_DIR = dirname(abspath(__file__))
except Exception as e:
    from sys import argv

    CMS_BOT_DIR = dirname(abspath(argv[0]))
#
# Processes a github issue to check if it is requesting the build of a new release
# If the issue is not requesting any release, it ignores it.
#

# -------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------

NOT_AUTHORIZED_MSG = "You are not authorized to request the build of a release."
CONFIG_MAP_FILE = CMS_BOT_DIR + "/config.map"
NO_ARCHS_FOUND_MSG = (
    "No architecures to build found for {rel_name}. Please check that you entered a "
    "valid release name or that the IBs are currently enabled for {queue}"
)
RELEASE_BASE_URL = "https://github.com/cms-sw/cmssw/releases/tag/%s"
BASE_BRANCH_URL = " https://github.com/cms-sw/cmssw/tree/%s"
RELEASE_CREATED_MSG = (
    "Release created: {rel_name}. The tag was created on top of branch: {base_branch}"
)
RELEASE_CREATION_FAIL_MSG = (
    "There was an error while attempting to create {rel_name}. "
    "Please check if it already exists https://github.com/cms-sw/cmssw/releases"
)
WRONG_RELEASE_NAME_MSG = "The release name is malformed. Please check for typos."
ACK_MSG = (
    "Request received. I will start to build the release after one of the following approve "
    'the issue: {approvers_list}. You can do this by writing "+1" in a '
    "comment.\n You can also ask me to begin to build cmssw-tool-conf first ( Cannot be done for patch releases ). To do this write "
    '"build cmssw-tool-conf" in a comment. I will start to build cmssw-tool-conf and then wait for the "+1" '
    "to start the build of the release.\n"
    "CMSSW Branch: {cmssw_queue}\n"
    "Architecture: {architecture}\n"
    "{cmssw_commit_tag}"
)
WATCHERS_MSG = "{watchers_list} you requested to watch the automated builds for {queue}"
QUEUING_BUILDS_MSG = (
    "Queuing Jenkins build for the following architectures: %s \n"
    'You can abort the build by writing "Abort" in a comment. I will delete the release, '
    "the cmssw and cmsdist tag, and close the issue. You can't abort the upload once at"
    " least one achitecture is being uploaded. \n"
    "If you are building cmssw-tool-conf first, I will wait for each architecture to finish to start the build of cmssw."
)
QUEUING_TOOLCONF_MSG = (
    "Queuing Jenkins build for cmssw-tool-conf for the following architectures: %s \n"
    'Be aware that I am building only cmssw-tool-conf. You still need to "+1" this issue to '
    "make me start the build of the release. For each architecture, I will only start to build "
    "the release after cmssw-tool-conf finishes building."
)
QUEING_UPLOADS_MSG = "Queing Jenkins upload for {architecture}"
CLEANUP_STARTED_MSG = "The cleanup has started for {architecture}"
NOT_TOOLCONF_FOR_PATCH_MSG = (
    "You cannot ask me to build cmssw-tool-conf for patch releases. Please delete that message."
)
JENKINS_CMSSW_X_Y_Z = "CMSSW_X_Y_Z"
JENKINS_ARCH = "ARCHITECTURE"
JENKINS_ISSUE_NUMBER = "ISSUE_NUMBER"
JENKINS_MACHINE_NAME = "MACHINE_NAME"
JENKINS_CMSSW_QUEUE = "CMSSW_QUEUE"
JENKINS_DOCKER_IMG = "DOCKER_IMG"
JENKINS_ONLY_TOOL_CONF = "ONLY_BUILD_TOOLCONF"
WRONG_NOTES_RELEASE_MSG = (
    'Previous release "{previous_release}" does not appear to be a valid release name'
)
PREVIOUS_RELEASE_NAME_MSG = 'Unable to find previous release for {release_name}. Please use "release-notes since <release>" in first line of the comment.'
GENERATING_RELEASE_NOTES_MSG = (
    "Generating release notes since {previous_release}. \n"
    "You can see the progress here: \n"
    "https://cmssdt.cern.ch/%s/job/release-produce-changelog/\n"
    "I will generate an announcement template.\n" % JENKINS_PREFIX
)
PROD_ARCH_NOT_READY_MSG = (
    "ATTENTION!!! The production architecture ({prod_arch}) is not ready yet. "
    "This needs to be checked before asking me to generate the release notes.\n"
    "When the production architecture is installed successfully, I will generate the release notes."
    " You don't need to write the command again."
)
REL_NAME_REGEXP = (
    "(CMSSW_[0-9]+_[0-9]+)_[0-9]+(_SLHC[0-9]*|)(_pre[0-9]+|_[a-zA-Z]*patch[0-9]+|)(_[^_]*|)"
)
UPLOAD_COMMENT = "upload %s"
UPLOAD_ALL_COMMENT = "^[uU]pload all$"
ABORT_COMMENT = "^[Aa]bort$"
RELEASE_NOTES_COMMENT = "^release-notes([ ]+since[ ]+[^ ]+)?$"
BUILD_TOOLCONF = "^[Bb]uild cmssw-tool-conf"
APPROVAL_COMMENT = "^[+]1$"
RELEASE_NOTES_GENERATED_LBL = "release-notes-requested"
ANNOUNCEMENT_GENERATED_LBL = "release-notes-requested"
JENKINS_PREV_RELEASE = "PREVIOUS_RELEASE"
JENKINS_RELEASE = "RELEASE"
JENKINS_PREV_CMSDIST_TAG = "PREVIOUS_CMSDIST_TAG"
JENKINS_CMSDIST_TAG = "CMSDIST_TAG"
JENKINS_PRODUCTION_ARCH = "PRODUCTION_ARCH"
JENKINS_BUILD_DIR = "BUILD_DIR"
ANNOUNCEMENT_TEMPLATE = (
    "Hi all,\n\n"
    "The {rel_type} {is_patch}release {rel_name} is now available "
    "for the following architectures:\n\n"
    "{production_arch} (production)\n"
    "{rest_of_archs}"
    "The release notes of what changed with respect to {prev_release} can be found at:\n\n"
    "https://github.com/cms-sw/cmssw/releases/{rel_name}\n"
    "{description}"
    "Cheers,\n"
    "cms-bot"
)

HN_REL_ANNOUNCE_EMAIL = "hn-cms-relAnnounce@cern.ch"
ANNOUNCEMENT_EMAIL_SUBJECT = "{rel_type} {is_patch}Release {rel_name} Now Available "
MAILTO_TEMPLATE = '<a href="mailto:{destinatary}?subject={sub}&amp;body={body}">here</a>'

# -------------------------------------------------------------------------------
# Statuses
# --------------------------------------------------------------------------------
# This is to determine the status of the issue after reading the labels

# The issue has just been created
NEW_ISSUE = "NEW_ISSUSE"
# The issue has been received, but it needs approval to start the build
PENDING_APPROVAL = "build-pending-approval"
# The build has been queued in jenkins
BUILD_IN_PROGRESS = "build-in-progress"
# The build has started
BUILD_STARTED = "build-started"
# The build has been aborted.
BUILD_ABORTED = "build-aborted"
# they requested to build cmssw-tool-conf and it is being built
TOOLCONF_BUILDING = "toolconf-building"
# at leas one of the architectures was built successully
BUILD_SUCCESSFUL = "build-successful"
# the builds are being uploaded
UPLOADING_BUILDS = "uploading-builds"
# the release has been announced
RELEASE_ANNOUNCED = "release-announced"
# the release was build without issues.
PROCESS_COMPLETE = "process-complete"
# Label for all Release Build Issue
RELEASE_BUILD_ISSUE = "release-build-request"

# -------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------


#
# creates a properties file to cleanup the build files.
#
def create_properties_file_cleanup(
    release_name, arch, issue_number, machine_name, tool_conf=False
):
    if tool_conf:
        out_file_name = "cleanup-tool-conf-%s-%s.properties" % (release_name, arch)
    else:
        out_file_name = "cleanup-%s-%s.properties" % (release_name, arch)

    if opts.dryRun:
        print("Not creating cleanup properties file (dry-run):\n %s" % out_file_name)
    else:
        print("Creating properties file for %s" % arch)
        out_file = open(out_file_name, "w")
        out_file.write("%s=%s\n" % (JENKINS_CMSSW_X_Y_Z, release_name))
        out_file.write("%s=%s\n" % (JENKINS_ARCH, arch))
        out_file.write("%s=%s\n" % (JENKINS_ISSUE_NUMBER, issue_number))
        out_file.write("%s=%s\n" % (JENKINS_MACHINE_NAME, machine_name))


# Creates a properties file in Jenkins to trigger the upload
# it needs to know the machine that was used for the build
#
def create_properties_files_upload(
    release_name, arch, issue_number, machine_name, docker_imgs, prod
):
    docker_img = ""
    if arch in docker_imgs:
        docker_img = docker_imgs[arch]
    out_file_name = "upload-%s-%s.properties" % (release_name, arch)
    if opts.dryRun:
        print("Not creating properties file (dry-run):\n %s" % out_file_name)
    else:
        print("Creating properties file for %s" % arch)
        out_file = open(out_file_name, "w")
        out_file.write("%s=%s\n" % (JENKINS_CMSSW_X_Y_Z, release_name))
        out_file.write("%s=%s\n" % (JENKINS_ARCH, arch))
        out_file.write("%s=%s\n" % (JENKINS_ISSUE_NUMBER, issue_number))
        out_file.write("%s=%s\n" % (JENKINS_DOCKER_IMG, docker_img))
        out_file.write("%s=%s\n" % (JENKINS_MACHINE_NAME, machine_name))
        out_file.write("%s=%s\n" % (JENKINS_PRODUCTION_ARCH, "true" if prod else "false"))


#
# Searches in the comments if there is a comment made from  the given users  that
# matches the given pattern. It returns the date of the first comment that matches
# if no comment matches it not returns None
#
def search_date_comment(comments, user_logins, pattern, first_line):
    for comment in reversed(comments):
        if comment.user.login not in user_logins:
            continue

        examined_str = comment.body

        if first_line:
            examined_str = str(
                comment.body.encode("ascii", "ignore").decode().split("\n")[0].strip("\n\t\r ")
            )

        if examined_str == pattern:
            return comment.created_at

        if re.match(pattern, examined_str):
            return comment.created_at

    return None


#
# Searches in the comments if there is a comment made from  the given users  that
# matches the given pattern. It returns a list with the matched comments.
#
def search_in_comments(comments, user_logins, pattern, first_line):
    found_comments = []
    requested_comment_bodies = [c.body for c in comments if c.user.login in user_logins]
    for body in requested_comment_bodies:
        examined_str = body
        if first_line:
            examined_str = str(
                body.encode("ascii", "ignore").decode().split("\n")[0].strip("\n\t\r ")
            )

        if examined_str == pattern:
            found_comments.append(body)
            continue

        if re.match(pattern, examined_str):
            found_comments.append(body)

    return found_comments


#
# Checks if the issue has already been seen so the issue will not be processed again
# Returns True if the issue needs to be processed, False if not
#
def check_if_already_processed(issue):
    comments = [c for c in issue.get_comments()]
    comment_bodies = [c.body for c in comments if c.user.login == "cmsbuild"]
    for body in comment_bodies:
        if "Release created" in body:
            return True
        if "Queuing Jenkins build" in body:
            return True
        if "You are not authorized" in body:
            return True

    return False


#
#  Creates the properties files to trigger the build in Jenkins
# if only_toolconf is selected, it adds a parameter to tell the script to only build cmssw-tool-conf
#
def create_properties_files(
    issue,
    release_name,
    architectures,
    issue_number,
    queue,
    docker_imgs,
    only_toolconf=False,
    cmsdist_commit=None,
):
    if not only_toolconf:
        for arch in architectures:
            remove_label(issue, arch + "-tool-conf-ok")
            add_label(issue, arch + "-build-queued")

    if opts.dryRun:
        print("Not creating properties files for (dry-run): %s" % ", ".join(architectures))
        return

    for arch in architectures:
        docker_img = ""
        if arch in docker_imgs:
            docker_img = docker_imgs[arch]
        out_file_name = "build-%s-%s.properties" % (release_name, arch)
        print("Creating properties file for %s" % arch)
        out_file = open(out_file_name, "w")
        out_file.write("%s=%s\n" % (JENKINS_CMSSW_X_Y_Z, release_name))
        out_file.write("%s=%s\n" % (JENKINS_ARCH, arch))
        out_file.write("%s=%s\n" % (JENKINS_ISSUE_NUMBER, issue_number))
        out_file.write("%s=%s\n" % (JENKINS_CMSSW_QUEUE, queue))
        out_file.write("%s=%s\n" % (JENKINS_DOCKER_IMG, docker_img))
        tool_conf_param = "true" if only_toolconf else "false"
        out_file.write("%s=%s\n" % (JENKINS_ONLY_TOOL_CONF, tool_conf_param))
        if cmsdist_commit:
            out_file.write("CMSDIST_HASH=%s\n" % cmsdist_commit)


#
# generates the properties file for triggering the release notes
# it infers the tag names based on te format REL/<release-name>/architecture
#
def create_properties_file_rel_notes(release_name, previous_release, architecture, issue_number):
    cmsdist_tag = "REL/" + release_name + "/" + architecture
    previos_cmsdist_tag = "REL/" + previous_release + "/" + architecture
    out_file_name = "release-notes.properties"

    if opts.dryRun:
        print("Not creating properties file (dry-run): %s" % out_file_name)
        return

    out_file = open(out_file_name, "w")
    out_file.write("%s=%s\n" % (JENKINS_PREV_RELEASE, previous_release))
    out_file.write("%s=%s\n" % (JENKINS_RELEASE, release_name))
    out_file.write("%s=%s\n" % (JENKINS_PREV_CMSDIST_TAG, previos_cmsdist_tag))
    out_file.write("%s=%s\n" % (JENKINS_CMSDIST_TAG, cmsdist_tag))
    out_file.write("%s=%s\n" % (JENKINS_ISSUE_NUMBER, issue_number))


#
# Creates a release in github
# If dry-run is selected it doesn't create the release and just prints that
# returns true if it was able to create the release, false if not
#
def get_release_github(repository, release_name):
    print("Checking release:\n %s" % release_name)
    request = Request(
        "https://api.github.com/repos/"
        + GH_CMSSW_ORGANIZATION
        + "/"
        + GH_CMSSW_REPO
        + "/releases/tags/"
        + release_name
    )
    try:
        print(urlopen(request).read())
        return True
    except Exception as e:
        print("There was an error while creating the release:\n", e)
        return False


def create_release_github(repository, release_name, branch, commit=None):
    if get_release_github(repository, release_name):
        return True
    if opts.dryRun:
        print("Not creating release (dry-run):\n %s" % release_name)
        return True

    print("Creating release:\n %s" % release_name)
    if commit:
        if not get_commit_info(GH_CMSSW_ORGANIZATION + "/" + GH_CMSSW_REPO, commit):
            sha = get_ref_commit(GH_CMSSW_ORGANIZATION + "/" + GH_CMSSW_REPO, commit)
            if sha:
                commit = sha
    else:
        commit = branch
    # creating releases will be available in the next version of pyGithub
    params = {
        "tag_name": release_name,
        "target_commitish": commit,
        "name": release_name,
        "body": "cms-bot is going to build this release",
        "draft": False,
        "prerelease": False,
    }
    print(params)
    request = Request(
        "https://api.github.com/repos/"
        + GH_CMSSW_ORGANIZATION
        + "/"
        + GH_CMSSW_REPO
        + "/releases",
        headers={"Authorization": "token " + GH_TOKEN},
    )
    request.get_method = lambda: "POST"
    print("--")
    try:
        print(urlopen(request, json.dumps(params).encode()).read())
        return True
    except Exception as e:
        print("There was an error while creating the release:\n", e)
        return False
    print()


#
# Deletes in github the release given as a parameter.
# If the release does no exists, it informs it in the message.
#
def delete_release_github(release_name):
    if opts.dryRun:
        print("Not deleting release (dry-run):\n %s" % release_name)
        return "Not deleting release (dry-run)"

    releases_url = (
        "https://api.github.com/repos/"
        + GH_CMSSW_ORGANIZATION
        + "/"
        + GH_CMSSW_REPO
        + "/releases?per_page=100"
    )

    request = Request(releases_url, headers={"Authorization": "token " + GH_TOKEN})
    releases = json.loads(urlopen(request).read())
    matchingRelease = [x["id"] for x in releases if x["name"] == release_name]

    if len(matchingRelease) < 1:
        return "Release %s not found." % release_name

    releaseId = matchingRelease[0]
    url = "https://api.github.com/repos/cms-sw/cmssw/releases/%s" % releaseId
    request = Request(url, headers={"Authorization": "token " + GH_TOKEN})
    request.get_method = lambda: "DELETE"

    try:
        print(urlopen(request).read())
        return "Release successfully deleted"
    except Exception as e:
        return "There was an error while deleting the release:\n %s" % e


def delete_tag(org, repo, tag):
    if not exists(repo):
        cmd = "mkdir deltag-{repo}; cd deltag-{repo}; git init; git remote add {repo} git@github.com:{org}/{repo}.git".format(
            org=org, repo=repo
        )
        print("Executing: \n %s" % cmd)
        status, out = run_cmd(cmd)
    cmd = "cd deltag-{repo}; git push {repo} :{tag}".format(repo=repo, tag=tag)
    print("Executing: \n %s" % cmd)
    status, out = run_cmd(cmd)
    print(out)
    if status != 0:
        msg = "I was not able to delete the tag %s. Probaly it had not been created." % tag
        print(msg)
        return msg
    msg = "%s tag %s successfully deleted." % (repo, tag)
    return msg


#
# Deletes in github the tag given as a parameter
#
def delete_cmssw_tag_github(release_name):
    if opts.dryRun:
        print("Not deleting cmssw tag (dry-run):\n %s" % release_name)
        return "Not deleting cmssw tag (dry-run): %s " % release_name
    return delete_tag(GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, release_name)


#
# for each architecture, gets the tag in cmsdist that should have ben created and deletes it
#
def delete_cmsdist_tags_github(release_name, architectures):
    result = ""
    for arch in architectures:
        tag_to_delete = "REL/{rel_name}/{architecture}".format(
            rel_name=release_name, architecture=arch
        )
        if opts.dryRun:
            msg = "Not deleting cmsdist tag (dry-run): %s" % tag_to_delete
            result += "\n\n  - " + msg
            continue
        result += "\n\n - " + delete_tag(GH_CMSSW_ORGANIZATION, GH_CMSDIST_REPO, tag_to_delete)
    return result


#
# Adds a label to the issue in github
# if dry-run is selected it doesn't add the label and just prints it
def add_label(issue, label):
    if opts.dryRun:
        print("Not adding label (dry-run):\n %s" % label)
        return
    print("Adding label:\n %s" % label)
    issue.add_to_labels(label)


#
# posts a message to the issue in github
# if dry-run is selected it doesn't post the message and just prints it
# if you set checkIfRepeated to False, if will not check if the message has already been written.
#
def post_message(issue, msg, checkIfRepeated=True):
    if opts.dryRun:
        print("Not posting message (dry-run):\n %s" % msg)
        return
    if checkIfRepeated and search_in_comments(comments, ["cmsbuild"], msg, False):
        print("Message already in the thread: \n %s" % msg)
        return
    print("Posting message:\n %s" % msg)
    issue.create_comment(msg)


#
# reads the comments and gets returns the status of the issue
#
def get_issue_status(issue):
    labels = [l.name for l in issue.get_labels() if l.name != RELEASE_BUILD_ISSUE]
    print("Issue Label: ", labels)

    if not labels:
        return NEW_ISSUE
    if BUILD_ABORTED in labels:
        return BUILD_ABORTED
    if PENDING_APPROVAL in labels:
        return PENDING_APPROVAL
    if BUILD_IN_PROGRESS in labels:
        return BUILD_IN_PROGRESS
    if TOOLCONF_BUILDING in labels:
        return TOOLCONF_BUILDING
    if BUILD_SUCCESSFUL in labels:
        return BUILD_SUCCESSFUL
    if UPLOADING_BUILDS in labels:
        return UPLOADING_BUILDS
    if RELEASE_ANNOUNCED in labels:
        return RELEASE_ANNOUNCED
    if PROCESS_COMPLETE in labels:
        return PROCESS_COMPLETE


#
# closes the issue
#
def close_issue(issue):
    if opts.dryRun:
        print("Not closing issue (dry-run)")
        return
    print("Closing issue...")
    issue.edit(state="closed")


#
# removes the labels of the issue
#
def remove_labels(issue):
    if opts.dryRun:
        print("Not removing issue labels (dry-run)")
        return
    issue.delete_labels()


# Removes a label form the issue
def remove_label(issue, label):
    if opts.dryRun:
        print("Not removing label (dry-run):\n %s" % label)
        return

    if label not in labels:
        print("label ", label, " does not exist. Not attempting to remove")
        return

    print("Removing label: %s" % label)
    try:
        issue.remove_from_labels(label)
    except Exception as e:
        print(e)
        from sys import exit

        exit(1)


#
# Creates a properties file in Jenkins to kill the build
# it needs to know the machine that was used for the build
#
def create_properties_kill_build(release_name):
    out_file_name = "kill-%s.properties" % (release_name)
    print("Creating properties file for %s" % release_name)
    out_file = open(out_file_name, "w")
    out_file.write("%s=%s\n" % (JENKINS_CMSSW_X_Y_Z, release_name))
    if opts.dryRun:
        out_file.write("DRY_RUN=true\n")
    else:
        out_file.write("DRY_RUN=false\n")


#
# Aborts the build:
# -Deletes the release in github
# -Deletes the cmssw tags
# -Deletes the cmsdist tags
# -Triggers the killing of the build process in jenkins
#
def abort_build(issue, release_name, architectures, comments):
    msg = "Deleting %s:" % release_name
    del_rel_result = delete_release_github(release_name)
    msg += "\n\n  - " + del_rel_result
    msg += "\n\n  - " + delete_cmssw_tag_github(release_name)

    create_properties_kill_build(release_name)
    msg += delete_cmsdist_tags_github(release_name, architectures)
    msg += "\n\n" + "You must create a new issue to start over the build."
    post_message(issue, msg)


#
# Classifies the labels and fills the lists with the details of the current
# status of each architecture
#
def fillDeatilsArchsLists(issue):
    labels = [l.name for l in issue.get_labels()]
    BUILD_OK.extend([x.split("-")[0] for x in labels if "-build-ok" in x])
    BUILDING.extend([x.split("-")[0] for x in labels if "-building" in x])
    UPLOAD_OK.extend([x.split("-")[0] for x in labels if "-upload-ok" in x])
    INSTALL_OK.extend([x.split("-")[0] for x in labels if "-installation-ok" in x])
    UPLOADING.extend([x.split("-")[0] for x in labels if "-uploading" in x])
    BUILD_ERROR.extend([x.split("-")[0] for x in labels if "-build-error" in x])
    TOOL_CONF_BUILDING.extend([x.split("-")[0] for x in labels if "-tool-conf-building" in x])
    TOOL_CONF_OK.extend([x.split("-")[0] for x in labels if "-tool-conf-ok" in x])
    TOOL_CONF_ERROR.extend([x.split("-")[0] for x in labels if "-tool-conf-error" in x])
    TOOL_CONF_WAITING.extend([x.split("-")[0] for x in labels if "-tool-conf-waiting" in x])
    TO_CLEANUP.extend(UPLOAD_OK + BUILD_ERROR + BUILD_OK + INSTALL_OK)


#
# Triggers the cleanup for the architectures in the list TO_CLEANUP
#
def triggerCleanup(issue, comments, release_name):
    if TO_CLEANUP:
        for arch in TO_CLEANUP:
            pattern = "The build has started for %s .*" % arch
            build_info_comments = search_in_comments(comments, ["cmsbuild"], pattern, False)

            pattern_tool_conf = "The cmssw-tool-conf build has started for %s .*" % arch
            tool_conf_info_comments = search_in_comments(
                comments, ["cmsbuild"], pattern_tool_conf, False
            )

            if not build_info_comments:
                print(
                    "No information found about the build machine, something is wrong for %s"
                    % arch
                )
                continue

            build_machine = build_info_comments[-1].split(" ")[7].strip(".")
            print("\nTriggering cleanup for %s" % arch)
            create_properties_file_cleanup(release_name, arch, issue.number, build_machine)

            if tool_conf_info_comments:
                build_machine_toolconf = tool_conf_info_comments[-1].split(" ")[8].strip(".")
                print("\nTriggering tool-conf cleanup for %s" % arch)
                create_properties_file_cleanup(
                    release_name, arch, issue.number, build_machine_toolconf, tool_conf=True
                )

            print()
            msg = CLEANUP_STARTED_MSG.format(architecture=arch)
            post_message(issue, msg)
            remove_label(issue, arch + "-upload-ok")
            remove_label(issue, arch + "-build-error")
            remove_label(issue, arch + "-build-ok")
            remove_label(issue, arch + "-installation-ok")
            add_label(issue, arch + "-finished")


#
# Creates the release in github, including the cmssw tag. It then creates the files to trigger the builds in jenkins
#
def start_release_build(
    issue,
    release_name,
    release_branch,
    architectures,
    docker_imgs,
    commit=None,
    cmsdist_commit=None,
):
    cmssw_repo = gh.get_repo(GH_CMSSW_ORGANIZATION + "/" + GH_CMSSW_REPO)
    release_created = create_release_github(cmssw_repo, release_name, release_branch, commit)
    if not release_created:
        msg = RELEASE_CREATION_FAIL_MSG.format(rel_name=release_name)
        post_message(issue, RELEASE_CREATION_FAIL_MSG.format(rel_name=release_name))
        exit(0)

    msg = RELEASE_CREATED_MSG.format(
        rel_name=(RELEASE_BASE_URL % release_name), base_branch=(BASE_BRANCH_URL % release_branch)
    )
    post_message(issue, msg)

    ready_to_build = list(
        set(architectures)
        - set(TOOL_CONF_WAITING)
        - set(TOOL_CONF_ERROR)
        - set(TOOL_CONF_BUILDING)
    )
    create_properties_files(
        issue,
        release_name,
        ready_to_build,
        issue.number,
        release_queue,
        docker_imgs,
        only_toolconf=False,
        cmsdist_commit=cmsdist_commit,
    )
    if ready_to_build:
        msg = QUEUING_BUILDS_MSG % ", ".join(ready_to_build)
        post_message(issue, msg)


#
# Creates the files to trigger the build of cmssw-tool-conf in jenkins.
#
def start_tool_conf_build(
    issue, release_name, release_branch, architectures, docker_imgs, cmsdist_commit=None
):
    create_properties_files(
        issue,
        release_name,
        architectures,
        issue.number,
        release_queue,
        docker_imgs,
        only_toolconf=True,
        cmsdist_commit=cmsdist_commit,
    )
    msg = QUEUING_TOOLCONF_MSG % ", ".join(architectures)
    post_message(issue, msg)


#
# removes the label for the current state and adds the label for the next state
#
def go_to_state(issue, current_state, new_state):
    print("\nSwitching to state: ", new_state, "\n")
    remove_label(issue, current_state)
    add_label(issue, new_state)


#
# Generates an announcement prototype
#
def fix_release_description(issue):
    if not issue.body:
        return "\n"
    desc_str = "\n" + issue.body.encode("ascii", "ignore").decode().strip() + "\n\n"
    desc_lines = []
    for l in desc_str.split("\n"):
        if "RELEASE_QUEUE:" in l:
            continue
        if "ARCHITECTURE:" in l:
            continue
        if "TAG_COMMIT:" in l:
            continue
        if "CMSSW_COMMIT:" in l:
            continue
        if "CMSDIST_COMMIT:" in l:
            continue
        if "PRODUCTION_ARCHITECTURE:" in l:
            continue
        desc_lines.append(l)
    return "\n".join(desc_lines)


def generate_announcement(
    release_name, previous_release_name, production_architecture, architectures
):
    print("\nGenerating announcement template...\n")
    is_development = "pre" in release_name
    type_str = "development" if is_development else "production"
    print("Is development: ", is_development)
    is_patch = "patch" in release_name
    patch_str = "patch " if is_patch else ""
    print("Is patch: ", is_patch)
    # The description of the issue should explain the reason for building the release
    desc = fix_release_description(issue)
    print("Description: \n", desc)

    architectures.remove(production_architecture)
    rest_of_archs = "\n".join(architectures) + "\n\n" if architectures else "\n"
    rel_cyc = "_".join(release_name.split("_")[:2])
    announcement = ANNOUNCEMENT_TEMPLATE.format(
        rel_type=type_str,
        is_patch=patch_str,
        rel_name=release_name,
        rel_cyc=rel_cyc,
        production_arch=production_architecture,
        rest_of_archs=rest_of_archs,
        prev_release=previous_release_name,
        description=desc,
    )

    return announcement


#
# Generates a link that the uset can click to write the announcement email with just one click
#
def generate_announcement_link(announcement, release_name):
    is_development = "pre" in release_name
    type_str = "Development" if is_development else "Production"
    is_patch = "patch" in release_name
    patch_str = "patch " if is_patch else ""

    subject = quote(
        ANNOUNCEMENT_EMAIL_SUBJECT.format(
            rel_type=type_str, is_patch=patch_str, rel_name=release_name
        )
    )

    msg = quote(announcement)
    link = MAILTO_TEMPLATE.format(destinatary=HN_REL_ANNOUNCE_EMAIL, sub=subject, body=msg)
    return link


#
# checks if the production architecture is ready, if so, it generates a template for the announcement
#
def check_if_prod_arch_ready(issue, prev_rel_name, production_architecture):
    if production_architecture in INSTALL_OK:
        print("Production architecture successfully installed..")
        # For now, it assumes that the release is being installed and it will be installed successfully
        announcement = generate_announcement(
            release_name, prev_rel_name, production_architecture, list(set(INSTALL_OK + UPLOAD_OK))
        )
        mailto = generate_announcement_link(announcement, release_name)
        msg = (
            "You can use this template for announcing the release:\n\n%s\n\n"
            "You can also click %s to send the email." % (announcement, mailto)
        )
        post_message(issue, msg, checkIfRepeated=False)
        add_label(issue, ANNOUNCEMENT_GENERATED_LBL)


#
# checks the issue for archs to be uploaded
#
def check_archs_to_upload(release_name, issue, docker_imgs, production_architecture):
    print("Looking for archs ready to be uploaded...\n")
    for arch in BUILD_OK:
        print("Ready to upload %s" % arch)
        pattern = "^The build has started for %s .*" % arch
        build_info_comments = search_in_comments(comments, ["cmsbuild"], pattern, True)
        if not build_info_comments:
            print("No information found about the build machine, something is wrong")
            exit(1)

        first_line_info_comment = str(
            build_info_comments[-1]
            .encode("ascii", "ignore")
            .decode()
            .split("\n")[0]
            .strip("\n\t\r ")
        )
        build_machine = first_line_info_comment.split(" ")[7].strip(".")
        print("Triggering upload for %s (prod arch: %s)" % (arch, arch == production_architecture))
        create_properties_files_upload(
            release_name,
            arch,
            issue.number,
            build_machine,
            docker_imgs,
            arch == production_architecture,
        )
        post_message(issue, QUEING_UPLOADS_MSG.format(architecture=arch))
        remove_label(issue, arch + "-build-ok")
        add_label(issue, arch + "-uploading")

    if BUILD_OK:
        return True
    else:
        return False


#
# checks if there are architectures that are ready to be built afer building tool-conf, and triggers the build if neccessary
#
def check_to_build_after_tool_conf(issue, release_name, release_queue, docker_imgs):
    print("Checking if there are architectures waiting to be started after building tool-conf")
    ready_to_build = TOOL_CONF_OK
    print(ready_to_build)
    create_properties_files(
        issue, release_name, ready_to_build, issue.number, release_queue, docker_imgs
    )
    if ready_to_build:
        msg = QUEUING_BUILDS_MSG % ", ".join(ready_to_build)
        post_message(issue, msg)


#
# Guesses the previous release name based on the name given as a parameter
#
def guess_prev_rel_name(release_name, issue):
    num_str = release_name.split("_")[-1]
    number = int(re.search("[0-9]+$", release_name).group(0))
    prev_number = number - 1
    prev_num_str = num_str.replace(str(number), str(prev_number))

    if ("patch" in num_str) or ("pre" in num_str):
        if prev_number < 1:
            if "pre" in num_str:
                post_message(issue, PREVIOUS_RELEASE_NAME_MSG.format(release_name=release_name))
                exit(0)
            return re.sub("_" + num_str + "$", "", release_name)
        return re.sub("_" + num_str + "$", "_" + prev_num_str, release_name)
    rel_match = (
        re.sub("_" + num_str + "$", "_" + prev_num_str, release_name)
        + "\(_[a-zA-Z]*patch[0-9][0-9]*\|\);"
    )
    if number == 0:
        rel_match = release_name + "_pre\([0-9][0-9]*\);"
    ret, out = run_cmd(
        "grep 'label="
        + rel_match
        + "' "
        + CMS_BOT_DIR
        + "/releases.map"
        + " | grep -v 'label="
        + release_name
        + ";' | tail -1 | sed 's|.*label=||;s|;.*||'"
    )
    return out


# -------------------------------------------------------------------------------
# Start of execution
# --------------------------------------------------------------------------------

if __name__ == "__main__":
    parser = OptionParser(usage="%prog <issue-id>")
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not post on Github",
        default=False,
    )
    parser.add_option(
        "-f",
        "--force",
        dest="force",
        action="store_true",
        help="Ignore previous comments in the issue and proccess it again",
        default=False,
    )
    parser.add_option(
        "-c",
        "--check-upload",
        dest="check_upload",
        action="store",
        help="Check if one of the authorized users has written the upload message"
        "for the architecture given as a parameter. It exits with 0 if it finds"
        "a message with the structure 'upload <architecture>', if not it exits"
        " with 1",
    )
    opts, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        parser.error("Too many arguments")

    GH_TOKEN = open(expanduser("~/.github-token")).read().strip()

    issue_id = int(args[0])
    gh = Github(login_or_token=GH_TOKEN)
    api_rate_limits(gh)
    cmssw_repo_name = GH_CMSSW_ORGANIZATION + "/" + GH_CMSSW_REPO
    cmssw_repo = gh.get_repo(cmssw_repo_name)
    issue = cmssw_repo.get_issue(issue_id)
    print("API Rate Limit")
    print("Limit, Remaining: ", gh.rate_limiting)
    print("Reset time (GMT): ", datetime.fromtimestamp(gh.rate_limiting_resettime))

    # 1. Is this a pull request?
    if issue.pull_request:
        print("This is a pull request, ignoring.")
        exit(0)

    title_match = re.match(BUILD_REL, issue.title)

    # 2. Is this issue meant to build a release?
    if not title_match:
        print("This issue is not for building a release, ignoring.")
        exit(0)

    comments = [c for c in issue.get_comments()]

    release_name = title_match.group(1)
    is_patch = "patch" in release_name
    full_release = release_name.split("patch")[0].rsplit("_", 1)[0] if is_patch else ""
    # Get the release queue from the release name.
    print(release_name)
    issue_body = ""
    if issue.body:
        issue_body = issue.body.encode("ascii", "ignore").decode().strip()
    release_queue = None
    rel_name_match = re.match(REL_NAME_REGEXP, release_name)
    if "RELEASE_QUEUE:" in issue_body:
        release_queue = issue_body.split("RELEASE_QUEUE:", 1)[1].split("\n", 1)[0].strip()
        print("Found forces release queue:", release_queue)
    else:
        if not rel_name_match:
            print("Release name not correctly formed")
            post_message(issue, WRONG_RELEASE_NAME_MSG)
            exit(0)

        release_queue = "".join(
            [x for x in rel_name_match.group(1, 4)]
            + ["_X"]
            + [x.strip("0123456789") for x in rel_name_match.group(2)]
        )

    release_tag_commit = None
    if "TAG_COMMIT:" in issue_body:
        release_tag_commit = issue_body.split("TAG_COMMIT:", 1)[1].split("\n", 1)[0].strip()
        print("Found forces commit:", release_tag_commit)

    if "CMSSW_COMMIT:" in issue_body:
        release_tag_commit = issue_body.split("CMSSW_COMMIT:", 1)[1].split("\n", 1)[0].strip()
        print("Found forces commit:", release_tag_commit)

    cmsdist_tag_commit = None
    if "CMSDIST_COMMIT:" in issue_body:
        cmsdist_tag_commit = issue_body.split("CMSDIST_COMMIT:", 1)[1].split("\n", 1)[0].strip()
        print("Found forces cmsdist commit:", cmsdist_tag_commit)

    sel_archs = []
    if "ARCHITECTURE:" in issue_body:
        sel_archs = set(
            issue_body.split("ARCHITECTURE:", 1)[1].split("\n", 1)[0].strip().split(",")
        )
        print("Found forces architectures:", sel_archs)

    print(release_queue, sel_archs)
    specs = get_config_map_properties({"DISABLED": "1", "IB_ONLY": "1"})
    architectures = [x["SCRAM_ARCH"] for x in specs if x["RELEASE_QUEUE"] == release_queue]
    if not architectures:
        print("Trying default queue")
        release_queue = "".join([x for x in rel_name_match.group(1, 2)] + ["_X"])
        print(release_queue)
        architectures = [x["SCRAM_ARCH"] for x in specs if x["RELEASE_QUEUE"] == release_queue]

    if sel_archs:
        architectures = [a for a in architectures if a in sel_archs]

    if is_patch:
        full_release_archs = get_full_release_archs(full_release)
        print("Full release archs:", full_release, full_release_archs)
        if not full_release_archs:
            msg = "Error: unable to find architectures for full release " + full_release
            post_message(issue, msg)
            exit(0)
        architectures = [a for a in architectures if a in full_release_archs]
        print("Patch release filtered archs:", architectures)

    # Check if we have at least one architecture to build and complain if not.
    if not architectures:
        print("no archs found for the requested release")
        msg = NO_ARCHS_FOUND_MSG.format(rel_name=release_name, queue=release_queue)
        post_message(issue, msg)
        exit(0)
    print("Archs: ", architectures)

    # Find out the docker images to be used for each arch
    docker_imgs = {}
    for x in specs:
        if (
            (x["RELEASE_QUEUE"] == release_queue)
            and ("DOCKER_IMG" in x)
            and (x["SCRAM_ARCH"] in architectures)
        ):
            docker_imgs[x["SCRAM_ARCH"]] = x["DOCKER_IMG"]
    print("Dockers:", docker_imgs)

    # Determine the release branch (which is the same as the release queue if not
    # specified) and start the build if needed.
    release_branches = [
        x["RELEASE_BRANCH"]
        for x in specs
        if (x["RELEASE_QUEUE"] == release_queue) and ("RELEASE_BRANCH" in x)
    ]

    possible_prod_arch = [
        x["SCRAM_ARCH"]
        for x in specs
        if (x["RELEASE_QUEUE"] == release_queue) and ("PROD_ARCH" in x)
    ]
    print("Debug:", release_name, release_queue, release_branches, possible_prod_arch)
    if len(architectures) > 1:
        err, production_architecture = run_cmd(
            CMS_BOT_DIR + "/get-production-arch %s %s" % (release_name, release_queue)
        )
        print("Debug", production_architecture)
        if err:
            print("Unable to find production architecture for the release")
            post_message(issue, "Unable to find production architecture for the release")
            exit(0)
        production_architecture = production_architecture.split("\n")[-1]
    else:
        production_architecture = architectures[0]

    if "PRODUCTION_ARCHITECTURE:" in issue_body:
        req_arch = issue_body.split("PRODUCTION_ARCHITECTURE:", 1)[1].split("\n", 1)[0].strip()
        if not req_arch in architectures:
            msg = (
                "You requested production architecutre to be %s but this is not a valid architecture for this release cycle."
                % req_arch
            )
            print(msg)
            post_message(issue, msg)
            exit(0)
        if is_patch and (production_architecture != req_arch):
            msg = (
                "You can not override production architecture for a patch release.\nProdction architecture for this release should be %s"
                % production_architecture
            )
            print(msg)
            post_message(issue, msg)
            exit(0)
        production_architecture = req_arch
        print("Found production architecture:", production_architecture)
    if not production_architecture and len(architectures) == 1:
        production_architecture = architectures[0]
    print("debug production arch: ", production_architecture)

    release_branch = release_queue

    if len(release_branches):
        release_branch = release_branches[0]

    # If a patch release is requested and there is a patchX branch, it will be used to tag the release. For example:
    # if you want to create CMSSW_7_1_4_patch2 and there exists a branch called CMSSW_7_1_4_patchX the tag will be
    # on top of the branch CMSSW_7_1_4_patchX instead of CMSSW_7_1_X.

    if is_patch:
        try:
            possible_branch = full_release + "_patchX"
            if get_branch(cmssw_repo_name, possible_branch)["name"] == possible_branch:
                release_branch = possible_branch
                print(
                    "This is a patch release and the branch %s was found. It will be used as base branch."
                    % possible_branch
                )
        except HTTPError as e:
            print(e)
            if e.code != 404:
                exit(1)

    print(release_branch)
    for rm in get_release_managers(release_branch):
        if not rm in APPROVE_BUILD_RELEASE:
            APPROVE_BUILD_RELEASE.append(rm)
        if not rm in REQUEST_BUILD_RELEASE:
            REQUEST_BUILD_RELEASE.append(rm)

    # 3. Is the author authorized to trigger a build?
    if not issue.user.login in REQUEST_BUILD_RELEASE:
        print("User not authorized")
        post_message(issue, NOT_AUTHORIZED_MSG)
        exit(0)

    # Get the status of this issue.
    status = get_issue_status(issue)
    print("Status: %s \n" % status)

    labels = [l.name for l in issue.get_labels()]
    print("Issue labels:", labels)

    BUILD_OK = []
    BUILDING = []
    UPLOAD_OK = []
    INSTALL_OK = []
    UPLOADING = []
    BUILD_ERROR = []
    TO_CLEANUP = []
    TOOL_CONF_BUILDING = []
    TOOL_CONF_OK = []
    TOOL_CONF_ERROR = []
    TOOL_CONF_WAITING = []
    # These lists are filled by fillDeatilsArchsLists( issue )

    fillDeatilsArchsLists(issue)

    if status == BUILD_ABORTED:
        print("Build Aborted. A new issue must be created if you want to build the release")

        date_aborted = search_date_comment(comments, APPROVE_BUILD_RELEASE, ABORT_COMMENT, True)
        # the time is 2 days because a new issue must be created to start again the build
        # if for the new build the build starts in the same machine as before, this will
        # start to delete the work directory of the new build.
        cleanup_deadline = datetime.now() - timedelta(days=2)
        if date_aborted < cleanup_deadline:
            print("Cleaning up since it is too old since it was aborted")
            triggerCleanup(issue, comments, release_name)
            close_issue(issue)
        else:
            print("Not too old yet to clean up")

    if status == NEW_ISSUE:
        approvers = ", ".join(["@" + x for x in APPROVE_BUILD_RELEASE])
        ALL_WATCHERS = yaml.load(open(CMS_BOT_DIR + "/build-release-watchers.yaml"), Loader=Loader)
        watchers = ALL_WATCHERS.get(release_queue)
        xqueue = release_queue
        if release_queue != release_branch:
            xqueue = release_queue + "(" + release_branch + ")"
        cmssw_commit_tag = ""
        if release_tag_commit:
            cmssw_commit_tag = "Release tag based on: %s\n" % release_tag_commit
        arch_msg = ", ".join(
            [
                a if a != production_architecture else "%s(%s)" % (a, "Production")
                for a in architectures
            ]
        )
        msg = ACK_MSG.format(
            approvers_list=approvers,
            cmssw_queue=xqueue,
            architecture=arch_msg,
            cmssw_commit_tag=cmssw_commit_tag,
        )

        if watchers:
            watchers_l = ", ".join(["@" + x for x in watchers])
            watchers_msg = WATCHERS_MSG.format(watchers_list=watchers_l, queue=release_queue)
            msg += watchers_msg

        post_message(issue, msg)
        add_label(issue, PENDING_APPROVAL)
        add_label(issue, RELEASE_BUILD_ISSUE)
        exit(0)

    if status == PENDING_APPROVAL:
        approval_comments = search_in_comments(
            comments, APPROVE_BUILD_RELEASE, APPROVAL_COMMENT, True
        )
        build_toolconf_commments = search_in_comments(
            comments, APPROVE_BUILD_RELEASE, BUILD_TOOLCONF, True
        )
        if build_toolconf_commments:
            if is_patch:
                post_message(issue, NOT_TOOLCONF_FOR_PATCH_MSG)
            else:
                start_tool_conf_build(
                    issue,
                    release_name,
                    release_branch,
                    architectures,
                    docker_imgs,
                    cmsdist_commit=cmsdist_tag_commit,
                )
                go_to_state(issue, status, TOOLCONF_BUILDING)
        elif approval_comments:
            start_release_build(
                issue,
                release_name,
                release_branch,
                architectures,
                docker_imgs,
                release_tag_commit,
                cmsdist_commit=cmsdist_tag_commit,
            )
            go_to_state(issue, status, BUILD_IN_PROGRESS)
        else:
            print("Build not approved or cmssw-tool-conf not requested yet")
            exit(0)

    if status == TOOLCONF_BUILDING:
        print("Waiting for approval to start the build")
        approval_comments = search_in_comments(
            comments, APPROVE_BUILD_RELEASE, APPROVAL_COMMENT, True
        )
        if approval_comments:
            print('Build approved, switching to "Build in Progress" state')

            # add a label for each arch for which tool conf has not started in jenkins
            tool_conf_reported = TOOL_CONF_BUILDING + TOOL_CONF_OK + TOOL_CONF_ERROR
            not_started = list(set(architectures) - set(tool_conf_reported))

            for arch in not_started:
                add_label(issue, arch + "-tool-conf-waiting")
                TOOL_CONF_WAITING.append(arch)

            go_to_state(issue, status, BUILD_IN_PROGRESS)
            start_release_build(
                issue,
                release_name,
                release_branch,
                architectures,
                docker_imgs,
                release_tag_commit,
                cmsdist_commit=cmsdist_tag_commit,
            )

    if status == BUILD_IN_PROGRESS:
        abort_comments = search_in_comments(comments, APPROVE_BUILD_RELEASE, ABORT_COMMENT, True)
        print(abort_comments)
        if abort_comments:
            print("Aborting")
            abort_build(issue, release_name, architectures, comments)
            go_to_state(issue, status, BUILD_ABORTED)
            exit(0)

        # if the previous state was to build tool-conf there are architectures for which it is needed to wait
        build_toolconf_commments = search_in_comments(
            comments, APPROVE_BUILD_RELEASE, BUILD_TOOLCONF, True
        )
        if build_toolconf_commments:
            check_to_build_after_tool_conf(issue, release_name, release_queue, docker_imgs)

        if BUILD_OK:
            go_to_state(issue, status, BUILD_SUCCESSFUL)

    if status == BUILD_SUCCESSFUL:
        abort_comments = search_in_comments(comments, APPROVE_BUILD_RELEASE, ABORT_COMMENT, True)
        print(abort_comments)
        if abort_comments:
            print("Aborting")
            abort_build(issue, release_name, architectures, comments)
            go_to_state(issue, status, BUILD_ABORTED)
            exit(0)

        # if the previous state was to build tool-conf there are architectures for which it is needed to wait
        build_toolconf_commments = search_in_comments(
            comments, APPROVE_BUILD_RELEASE, BUILD_TOOLCONF, True
        )
        if build_toolconf_commments:
            check_to_build_after_tool_conf(issue, release_name, release_queue, docker_imgs)

        upload_all_requested = search_in_comments(
            comments, APPROVE_BUILD_RELEASE, UPLOAD_ALL_COMMENT, True
        )

        if upload_all_requested:
            check_archs_to_upload(release_name, issue, docker_imgs, production_architecture)
            go_to_state(issue, status, UPLOADING_BUILDS)
        else:
            print("Upload not requested yet")

    if status == UPLOADING_BUILDS:
        # upload archs as soon as they get ready
        check_archs_to_upload(release_name, issue, docker_imgs, production_architecture)

        # Check if someone asked for release notes, go to next state after generating notes.
        # At least one architecture must have been successfully installed
        if INSTALL_OK and (RELEASE_NOTES_GENERATED_LBL not in labels):
            print("checking if someone asked for the release notes")
            release_notes_comments = search_in_comments(
                comments, APPROVE_BUILD_RELEASE, RELEASE_NOTES_COMMENT, True
            )

            if release_notes_comments:
                comment = release_notes_comments[-1]
                first_line = str(
                    comment.encode("ascii", "ignore").decode().split("\n")[0].strip("\n\t\r ")
                )
                comment_parts = first_line.strip().split(" ")
                print("debug: ", comment_parts)

                if len(comment_parts) > 1:
                    prev_rel_name = comment_parts[2].rstrip()
                else:
                    prev_rel_name = guess_prev_rel_name(release_name, issue)
                    print(prev_rel_name)

                rel_name_match = re.match(REL_NAME_REGEXP, prev_rel_name)
                if not rel_name_match:
                    msg = WRONG_NOTES_RELEASE_MSG.format(previous_release=prev_rel_name)
                    post_message(issue, msg)
                    exit(0)

                if production_architecture not in INSTALL_OK:
                    msg = PROD_ARCH_NOT_READY_MSG.format(prod_arch=production_architecture)
                    post_message(issue, msg)
                    exit(0)
                create_properties_file_rel_notes(
                    release_name, prev_rel_name, production_architecture, issue.number
                )
                msg = GENERATING_RELEASE_NOTES_MSG.format(previous_release=prev_rel_name)
                post_message(issue, msg)
                add_label(issue, RELEASE_NOTES_GENERATED_LBL)

                # Check if the production architecture was uploaded and was correctly installed, generate announcement if so.
                check_if_prod_arch_ready(issue, prev_rel_name, production_architecture)
                go_to_state(issue, status, RELEASE_ANNOUNCED)

    if status == RELEASE_ANNOUNCED:
        # upload archs as soon as they get ready
        check_archs_to_upload(release_name, issue, docker_imgs, production_architecture)

        print("checking if someone asked again for the release notes")
        release_notes_comments = search_in_comments(
            comments, APPROVE_BUILD_RELEASE, RELEASE_NOTES_COMMENT, True
        )
        generating_release_notes_comments = search_in_comments(
            comments, ["cmsbuild"], "Generating release notes", True
        )

        if len(release_notes_comments) > len(generating_release_notes_comments):
            print("I need to generate the release notes again")
            # check if this is beter if a function is added
            comment = release_notes_comments[-1]
            first_line = str(
                comment.encode("ascii", "ignore").decode().split("\n")[0].strip("\n\t\r ")
            )
            comment_parts = first_line.strip().split(" ")

            if len(comment_parts) > 1:
                prev_rel_name = comment_parts[2].rstrip()
            else:
                prev_rel_name = guess_prev_rel_name(release_name, issue)
                print(prev_rel_name)

            rel_name_match = re.match(REL_NAME_REGEXP, prev_rel_name)
            if not rel_name_match:
                msg = WRONG_NOTES_RELEASE_MSG.format(previous_release=prev_rel_name)
                post_message(issue, msg, checkIfRepeated=False)
                exit(0)

            create_properties_file_rel_notes(
                release_name, prev_rel_name, production_architecture, issue.number
            )
            msg = GENERATING_RELEASE_NOTES_MSG.format(previous_release=prev_rel_name)
            post_message(issue, msg, checkIfRepeated=False)
            check_if_prod_arch_ready(issue, prev_rel_name, production_architecture)

        # check if the cleanup has been requested or if 2 days have passed since the release-notes were generated.
        print("Checking if someone requested cleanup, or the issue is too old...")
        date_rel_notes = search_date_comment(
            comments, APPROVE_BUILD_RELEASE, RELEASE_NOTES_COMMENT, True
        )
        cleanup_deadline = datetime.now() - timedelta(days=2)
        if date_rel_notes:
            too_old = date_rel_notes < cleanup_deadline
        else:
            too_old = False
        pattern = "^cleanup$"
        cleanup_requested_comments = search_in_comments(
            comments, APPROVE_BUILD_RELEASE, pattern, True
        )
        if cleanup_requested_comments or too_old:
            triggerCleanup(issue, comments, release_name)
            close_issue(issue)
            go_to_state(issue, status, PROCESS_COMPLETE)
