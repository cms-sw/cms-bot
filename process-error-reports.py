#!/usr/bin/env python3

# This script will be famous:
#
# Parses logs looking for errors.
# Parses github issues looking for past errors.
# Updates past errors to match the current status.

from argparse import ArgumentParser
from glob import glob
from github import Github, Label
from os.path import basename, join, expanduser, exists
from _py2with3compatibility import run_cmd
import re
import hashlib
from operator import itemgetter
from socket import setdefaulttimeout

setdefaulttimeout(120)

PING_COMMENT = "This issue is also present in release %s"
RESULTS_RE = "^([0-9.]+)_([^ ]*) (.*) - time date.*exit: (.*)"
FAILED_RE = "Step([0-9])-FAILED"


# Create a regular expression from a format string.
# - Replace format strings with something does not enter the substitutions below.
# - Replace regexp special caratecters with their escaped counter parts
# - Replace back @@@ to be "(.*)" for the matching
def reEscape(s):
    s = re.sub("%\([a-z_A-Z]+\)s", "@@@", s)
    s = re.sub("([\[\]\(\)\*\+\.])", "\\\\\\1", s)
    s = s.replace("\n", "\\n")
    s = re.sub("@@@", "(.*)", s)
    return s


RELVAL_ISSUE_TITLE = (
    '%(id_ib)s has "%(error_title)s" issue in %(id_release)s. ERROR_ID:%(error_hash)s'
)
RELVAL_ISSUE_SUMMARY = "The following error:\n\n```\n%(error_text)s\n\n```\n\nis found in the following *(workflow, step)* pairs:\n\n%(steps)s\nClick on the link for more information."
RELVAL_ISSUE_LINK_TEMPLATE = "- [Workflow %(workflowId)s - Step %(step)s](https://cmssdt.cern.ch/SDT/jenkins-artifacts/summary-merged-prs/merged_prs.html)"

ISSUE_TITLE_MATCHER = reEscape(RELVAL_ISSUE_TITLE)
ISSUE_BODY_MATCHER = reEscape(RELVAL_ISSUE_SUMMARY)
ISSUE_LINK_MATCHER = reEscape(RELVAL_ISSUE_LINK_TEMPLATE)


def format(s, **kwds):
    return s % kwds


# Parses the report with all the failing steps
def parseSteps(buf):
    results = []
    for l in buf.split("\n"):
        m = re.match(ISSUE_LINK_MATCHER, l)
        if not m:
            continue
        print(m.groups())
        results.append({"workflow": str(m.group(1)), "step": int(m.group(2))})
    return results


def readWorkflows(f):
    buf = f.read()
    results = {}
    for l in buf.split("\n"):
        r = re.match(RESULTS_RE, l)
        if not r:
            continue
        workflowId, workflow, steps, exit = r.groups()
        steps = steps.split(" ")
        failedSteps = [
            int(re.match(FAILED_RE, s).group(1)) + 1 for s in steps if re.match(FAILED_RE, s)
        ]
        if not failedSteps:
            continue
        results[workflowId] = {"workflowId": workflowId, "name": workflow, "steps": failedSteps}
    return results


def postNewMessage(
    dryRun=True,
    labels=None,
    repo=None,
    queue=None,
    error_title=None,
    workflows=None,
    current_release=None,
    error_hash=None,
    error_text=None,
    **kwds,
):
    if labels is None:
        labels = []
    if workflows is None:
        workflows = []
    steps = ""
    print("foo" + str(workflows[0]))
    workflows.sort(key=itemgetter("workflowId"))
    for info in workflows[:20]:
        steps += (
            format(
                RELVAL_ISSUE_LINK_TEMPLATE,
                step=step,
                workflowId=info["workflowId"],
                name=info["name"],
            )
            + "\n"
        )
    if len(workflows) > 20:
        steps += "- .. and %s more not listed here." % (len(workflows) - 20)
    title = format(
        RELVAL_ISSUE_TITLE,
        id_ib=queue,
        id_release=current_release,
        error_title=error_title,
        error_hash=error_hash,
    )
    body = format(
        RELVAL_ISSUE_SUMMARY,
        error_text=error_text,
        steps=steps,
        full_message_url="foo",
    )
    print("\n---")
    print("The following message will be added:")
    print(title)
    print(body)
    if dryRun:
        print("--dry-run specified. Not adding new messages")
        return
    repo.create_issue(title=title, body=body, labels=labels)


def updateBugReport(dryRun=False, error_text="", workflows=[], issue=None, **kwds):
    print(workflows)
    workflows.sort(key=itemgetter("workflowId"))
    links = [RELVAL_ISSUE_LINK_TEMPLATE % s for s in workflows]
    if len(links) > 20:
        links = links[:20] + ["- .. and %s more" % (len(links) - 20)]
    steps = "\n".join(links) + "\n"
    body = format(RELVAL_ISSUE_SUMMARY, error_text=error_text, steps=steps, full_message_url="foo")
    print("Issue %s will be updated as follows" % issue.number)
    print(body)
    oldBody = issue.body.split("\n")

    if dryRun:
        print("--dry-run specified. Not adding new messages")
        return
    issue.edit(body=body)


def getZippedLog(name, t, p, info):
    zippedLogs = "%s/pyRelValMatrixLogs.zip" % p
    print(info)
    info["step"] = info["steps"][0]
    logFile = "%(workflowId)s_%(name)s/step%(step)s_%(name)s.log" % info
    print(logFile)
    print(join(p, "pyRelValMatrixLogs.zip"))
    if not exists(join(p, "pyRelValMatrixLogs.zip")):
        return None
    cmd = "unzip -cx %s %s" % (zippedLogs, logFile)
    print(cmd)
    err, out = run_cmd("unzip -cx %s %s" % (zippedLogs, logFile))
    if err:
        return None
    return out


# Return (hash, title, errorMessage) if I can
# understand the error message. False otherwise.
def understandAssertion(name, t, p, info):
    log = getZippedLog(name, t, p, info)
    if not log:
        return None
    checkAssertion = re.findall(".*/src/(.*/src/.*): Assertion `(.*)' failed.", log)
    if len(checkAssertion) == 0:
        return None

    print("Reporting this as an assertion")
    errorTitle = "failed assertion"
    uniqueMessage = checkAssertion[0][1]
    errorMessage = "%s: Assertion `%s' failed." % (checkAssertion[0][0], checkAssertion[0][1])
    h = hashlib.sha1((name + errorTitle + uniqueMessage).encode()).hexdigest()[:10]
    return (h, errorTitle, errorMessage)


# Understand fatal root errors
def understandFatalRootError(name, t, p, info):
    print("Attempt with root error")
    log = getZippedLog(name, t, p, info)
    if not log:
        print("Log not found")
        return None
    print(len(log))
    print(not "----- Begin Fatal Exception" in log)
    if not "----- Begin Fatal Exception" in log:
        return None
    matcher = str(
        ".*An exception of category 'FatalRootError' occurred.*"
        ".*Fatal Root Error: [@]SUB=([^\n]*)(.*)\n"
    )
    s = log.split("----- Begin Fatal Exception")[1].split("----- End Fatal Exception")[0]
    s = s.split("\n", 1)[1]
    checkRootError = re.findall(matcher, s, re.DOTALL)
    print("root error %s" % str(checkRootError))
    if not checkRootError:
        return None
    errorTitle = re.sub("/.*/", "", checkRootError[0][1].strip("\n"))
    # Remove any paths.
    errorMessage = re.sub("/.*/", "", s).strip("\n")
    h = hashlib.sha1((name + errorTitle + errorMessage).encode()).hexdigest()[:10]
    print(h)
    return (h, errorTitle, errorMessage)


# Understand if there was a missing input file error.
# - Fails in step2.
def understandStep1Error(name, t, p, info):
    if int(info["steps"][0]) != 2:
        return
    zippedLogs = "%s/pyRelValMatrixLogs.zip" % p
    logFile = "%(workflowId)s_%(name)s/step1_dasquery.log" % info
    if not exists(join(p, "pyRelValMatrixLogs.zip")):
        return None
    cmd = "unzip -qq -cx %s %s 2>/dev/null" % (zippedLogs, logFile)
    print(cmd)
    err, out = run_cmd(cmd)
    if err:
        return None
    if out.strip():
        return None
    errorTitle = "cannot find input"
    errorMessage = str(
        "step2 fails when looking for input.\n"
        "Input file might have been deleted or we have a DAS issue."
    )
    h = hashlib.sha1((name + errorTitle).encode()).hexdigest()[:10]
    return (h, errorTitle, errorMessage)


# Generic "catch all" solution for errors. This must be last in the list of
# understanding plugins.
def understandGenericError(name, t, p, info):
    errorTitle = "generic error"
    errorMessage = "I could not fully undestand what is going on, but some relval fails.\nPlease have a look at the errors."
    h = hashlib.sha1((name + "generic error").encode()).hexdigest()[:10]
    return (h, errorTitle, errorMessage)


understandingPlugins = [
    understandStep1Error,
    understandAssertion,
    understandFatalRootError,
    understandGenericError,
]


def understandError(name, t, p, info):
    """returns a tuple with a unique hash identifyingh this error
    and a human readable message trying to explain it.
    """
    # For the moment we simply have a generic error and
    # we include the release queue in the hash so that we
    # have errors being generated separately per release queue
    for plugin in understandingPlugins:
        result = plugin(name, t, p, info)
        if not result:
            continue
        return result
    assert False


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--logdir", type=str, help="where to find the logs")
    parser.add_argument("--filter", type=str, default="")
    parser.add_argument("-n", "--dry-run", dest="dryRun", action="store_true", default=False)
    args = parser.parse_args()
    print(args.dryRun)

    # Generate a tuple with
    # (<release-name>, <release-queue>, <release-path>)
    globExpr = join(args.logdir, "*/www/*/*/*")
    print(globExpr)
    releases = [r for r in glob(globExpr) if re.match(".*" + args.filter + ".*", r)]
    RESULTS_PATH = "pyRelValMatrixLogs/run/runall-report-step123-.log"
    releases = [r for r in releases if exists(join(r, RESULTS_PATH))]
    names = sorted([basename(r) for r in releases])
    names.reverse()
    types = []
    last_names = []
    for x in names:
        if x.split("_X")[0] in types:
            continue
        types.append(x.split("_X")[0])
        last_names.append(x)

    types = [x + "_X" for x in types]
    last_releases = []
    for r in releases:
        for l in last_names:
            if l in r:
                last_releases.append(r)
    last_releases.sort()
    release_info = zip(last_names, types, last_releases)

    for x in release_info:
        print("The following releases will be considered: ")
        print("\n".join(["- %s for %s" % (x[0], x[1]) for x in release_info]))

    # Iterate on the latest releases and find out if they have issues, producing
    # a map of workflows steps which are broken.
    print("Parsing new issues")
    validErrorReport = {}
    for name, t, p in release_info:
        errorLogPath = join(p, "pyRelValMatrixLogs/run/runall-report-step123-.log")
        if not exists(errorLogPath):
            print("Cannot find %s" % errorLogPath)
            continue
        # print errorLogPath
        print("Processing %s" % errorLogPath)
        workflows = readWorkflows(open(errorLogPath))
        if not workflows:
            continue
        # If we have error report we construct a hash which uniquely identifies the
        # error (by hashing error message and release) and append all broken
        # steps to it.
        for workflow, info in workflows.items():
            for step in info["steps"]:
                (h, errorTitle, errorMessage) = understandError(name, t, p, info)
                if not h in validErrorReport:
                    validErrorReport[h] = {
                        "queue": t,
                        "current_release": name,
                        "error_title": errorTitle,
                        "error_text": errorMessage,
                        "error_hash": h,
                        "workflows": [],
                    }
            print(workflow, step)
            stepInfo = {"workflowId": info["workflowId"], "name": info["name"], "step": step}
            validErrorReport[h]["workflows"].append(stepInfo)

    print("Parsing old issues.")
    # Get from github all the issues which are associated to failing relvals.
    # Parse them to have an understanding of current status.
    issues = []
    gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
    repo = gh.get_organization("cms-sw").get_repo("cmssw")
    labels = repo.get_labels()
    relvalIssueLabel = [x for x in labels if x.name == "relval"]
    issues = repo.get_issues(labels=relvalIssueLabel)
    print("Old issues found: " + ", ".join(["#%s" % x.number for x in issues]))
    pastIssues = {}
    for issue in issues:
        tm = re.match(ISSUE_TITLE_MATCHER, issue.title, re.DOTALL)
        if not tm:
            print("Unable to parse title %s for issue %s" % (issue.title, issue.number))
            continue
        parts = tm.groups()
        queue, error_title, first_release, error_hash = parts

        if not error_hash in pastIssues:
            pastIssues[error_hash] = {
                "queue": queue,
                "first_release": first_release,
                "error_hash": error_hash,
                "workflows": [],
                "issue": issue,
            }

        # Parse the body to try to understand the previous set of failing tests.
        # If the format of the report changed, this is handle by simply rewriting
        # the body completely.
        bm = re.match(ISSUE_BODY_MATCHER, issue.body, re.DOTALL)
        if not bm:
            print("Unable to parse body for issue %s. Issue will be updated" % (issue.number))
            continue
        parts = bm.groups()
        error_message, workflows = parts
        pastIssues[error_hash]["workflows"] = parseSteps(workflows)

    print("Updating current status")
    # Do the matching between current status and old status.
    # Iterate on new status:
    # - If an error was not reported. Add a new message
    # - If an error was already reported, for a different
    #   set of steps, update the list of steps.
    # - If an error was already reported, do not do anything.
    #
    for h, payload in validErrorReport.items():
        if not h in pastIssues:
            print("New error detected for %s. Will post a message" % payload["queue"])
            postNewMessage(dryRun=args.dryRun, repo=repo, labels=relvalIssueLabel, **payload)
            continue

        currentSteps = payload["workflows"]
        pastSteps = pastIssues[h]["workflows"]
        currentSteps = sorted([(float(x["workflowId"]), x["step"]) for x in currentSteps])
        pastSteps = sorted([(float(x["workflow"]), x["step"]) for x in pastSteps])

        if currentSteps == pastSteps:
            print("No changes in issue %s." % pastIssues[h]["issue"].number)
            continue

        issue = pastIssues[h]["issue"]
        print(
            "Error %s is already found in github, but changed. Adapting description."
            % issue.number
        )
        updateBugReport(dryRun=args.dryRun, issue=issue, **payload)

    for h, payload in list(pastIssues.items()):
        if h in validErrorReport:
            continue
        # Skip the queues which we have filtered.
        if not re.match(".*" + args.filter + ".*", payload["queue"]):
            continue
        if args.dryRun:
            print("Issue %s should really be closed." % payload["issue"].number)
        else:
            print("Closing issue %s." % payload["issue"].number)
            issue.edit(state="closed")
