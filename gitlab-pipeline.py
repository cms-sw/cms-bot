#!/usr/bin/env python3
"""
Trigger a GitLab CI pipeline with a pipeline trigger token and/or wait for a
pipeline to finish.

Examples:
  # Trigger only; the pipeline id and URL are written to pipeline.json
  gitlab-pipeline.py -p group/project -t /path/to/trigger-token -r main \\
      -v KEY1=value1 -v KEY2=value2 -o pipeline.json

  # Wait for an already triggered pipeline
  gitlab-pipeline.py -p group/project -i 12345 -w --timeout 7200 -o pipeline.json

Tokens are read from files so that they never show up on the command line or
in the "set -x" trace of the calling shell script.

Exit codes (1 and 2 are left to the python interpreter and to argparse):
  0  pipeline triggered and, with --wait, finished successfully
  3  pipeline finished without success (failed, canceled, skipped or blocked
     on a manual job)
  4  timed out waiting for the pipeline
  5  could not trigger the pipeline or lost contact with GitLab
  6  interrupted, e.g. the Jenkins job was aborted
"""

import argparse
import json
import re
import signal
import sys
import time
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

EXIT_OK = 0
EXIT_FAILED = 3
EXIT_TIMEOUT = 4
EXIT_ERROR = 5
EXIT_ABORTED = 6

# https://docs.gitlab.com/api/pipelines/ : every other status means "not finished yet"
FAILED_STATES = ("failed", "canceled", "skipped", "manual")
# Polling again does not help for these HTTP errors
FATAL_HTTP_CODES = (401, 403, 404)


class Aborted(Exception):
    pass


class GitLabError(Exception):
    def __init__(self, message, fatal=False):
        Exception.__init__(self, message)
        self.fatal = fatal


def log(msg):
    try:
        print("[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)
    except OSError:
        # Whoever was reading our output is gone, e.g. the job was aborted. Carry on
        pass


def read_token(path):
    try:
        with open(path) as ref:
            return ref.read().strip()
    except OSError as e:
        raise GitLabError("unable to read the token file: %s" % e)


def api_call(url, data=None, token=None, timeout=60):
    """GET url, or POST it if data is given. Returns the decoded JSON reply."""
    headers = {"Accept": "application/json"}
    if token:
        headers["PRIVATE-TOKEN"] = token
    body = None
    if data is not None:
        body = urlencode(data).encode("utf-8")
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        # Only report the reply of the server: the request can contain a token
        reply = e.read().decode("utf-8", "replace").strip()[:300]
        raise GitLabError("HTTP %s: %s" % (e.code, reply), e.code in FATAL_HTTP_CODES)
    except (OSError, HTTPException, ValueError) as e:
        raise GitLabError("%s: %s" % (type(e).__name__, e))


def save(output, pipeline, result):
    if not output:
        return
    data = {
        "id": pipeline.get("id"),
        "web_url": pipeline.get("web_url", ""),
        "status": pipeline.get("status", ""),
        "result": result,
    }
    with open(output, "w") as ref:
        json.dump(data, ref, indent=2)
        ref.write("\n")


def trigger_pipeline(api, ref, token, variables):
    data = [("token", token), ("ref", ref)]
    data += [("variables[%s]" % name, value) for name, value in variables]
    return api_call("%s/trigger/pipeline" % api, data=data)


def wait_for_pipeline(api, pipeline, token, timeout, poll, max_errors):
    """Poll the pipeline until it finishes. Returns (exit code, result)."""
    deadline = time.time() + timeout
    last_status = None
    errors = 0
    while True:
        try:
            pipeline.update(api_call("%s/pipelines/%s" % (api, pipeline["id"]), token=token))
            errors = 0
        except GitLabError as e:
            errors += 1
            log("Unable to get the pipeline status (%s/%s): %s" % (errors, max_errors, e))
            if e.fatal:
                log("Is the project public, or does the API token have read access to it?")
            if e.fatal or (errors >= max_errors):
                return EXIT_ERROR, "error"
        else:
            status = pipeline.get("status")
            if status != last_status:
                log("Pipeline %s is %s: %s" % (pipeline["id"], status, pipeline.get("web_url")))
                last_status = status
            if status == "success":
                return EXIT_OK, "success"
            if status in FAILED_STATES:
                return EXIT_FAILED, "failed"
        remaining = deadline - time.time()
        if remaining <= 0:
            log("Pipeline %s did not finish within %s seconds" % (pipeline["id"], timeout))
            return EXIT_TIMEOUT, "timeout"
        time.sleep(min(poll, remaining))


def cancel_pipeline(api, pipeline, token):
    try:
        api_call("%s/pipelines/%s/cancel" % (api, pipeline["id"]), data=[], token=token)
        log("Canceled pipeline %s" % pipeline["id"])
    except GitLabError as e:
        log("Unable to cancel pipeline %s: %s" % (pipeline["id"], e))


def on_signal(signum, frame):
    raise Aborted()


def variable(value):
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", value):
        raise argparse.ArgumentTypeError("%r is not of the form KEY=VALUE" % value)
    return tuple(value.split("=", 1))


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-u", "--url", default="https://gitlab.cern.ch", help="GitLab server")
    parser.add_argument(
        "-p", "--project", required=True, help="Project path (group/project) or numeric id"
    )
    parser.add_argument("-o", "--output", help="Write pipeline id, URL and result to this file")
    group = parser.add_argument_group("trigger a pipeline")
    group.add_argument("-t", "--trigger-token", metavar="FILE", help="File with the trigger token")
    group.add_argument("-r", "--ref", default="main", help="Branch or tag to run the pipeline on")
    group.add_argument(
        "-v",
        "--variable",
        metavar="KEY=VALUE",
        type=variable,
        action="append",
        default=[],
        help="CI/CD variable for the pipeline, can be repeated",
    )
    group = parser.add_argument_group("wait for a pipeline")
    group.add_argument("-w", "--wait", action="store_true", help="Wait for the pipeline to finish")
    group.add_argument("-i", "--pipeline", type=int, help="Wait for this pipeline, do not trigger")
    group.add_argument(
        "-a",
        "--api-token",
        metavar="FILE",
        help="File with an access token (read_api) to get the pipeline status. "
        "Not needed if the pipelines of the project are public",
    )
    group.add_argument("--timeout", type=int, default=14400, help="Seconds to wait")
    group.add_argument("--poll", type=int, default=60, help="Seconds between status checks")
    group.add_argument("--max-errors", type=int, default=10, help="Consecutive failed checks")
    group.add_argument(
        "--cancel-on-abort",
        action="store_true",
        help="Cancel the pipeline if this script is interrupted (the access token needs api scope)",
    )
    args = parser.parse_args()
    if args.pipeline and args.trigger_token:
        parser.error("use either --trigger-token or --pipeline")
    if not args.trigger_token and not (args.pipeline and args.wait):
        parser.error("nothing to do: use --trigger-token and/or --pipeline with --wait")
    return args


def main():
    args = parse_args()
    api = "%s/api/v4/projects/%s" % (args.url.rstrip("/"), quote(args.project, safe=""))
    pipeline = {"id": args.pipeline}
    try:
        api_token = read_token(args.api_token) if args.api_token else None
    except GitLabError as e:
        log(e)
        return EXIT_ERROR
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    try:
        if args.trigger_token:
            try:
                reply = trigger_pipeline(
                    api, args.ref, read_token(args.trigger_token), args.variable
                )
                pipeline = {"id": reply["id"], "web_url": reply.get("web_url", "")}
                pipeline["status"] = reply.get("status", "")
            except (GitLabError, KeyError, TypeError) as e:
                log("Unable to trigger a pipeline for %s: %s" % (args.project, e))
                return EXIT_ERROR
            log("Triggered pipeline %s: %s" % (pipeline["id"], pipeline["web_url"]))
            save(args.output, pipeline, "triggered")
        if not args.wait:
            return EXIT_OK
        code, result = wait_for_pipeline(
            api, pipeline, api_token, args.timeout, args.poll, args.max_errors
        )
        save(args.output, pipeline, result)
        return code
    except Aborted:
        log("Interrupted")
        # Do not let a second signal interrupt the cleanup
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if pipeline["id"]:
            if args.cancel_on_abort:
                cancel_pipeline(api, pipeline, api_token)
            save(args.output, pipeline, "aborted")
        return EXIT_ABORTED


if __name__ == "__main__":
    sys.exit(main())
