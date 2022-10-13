import functools
import os
import re


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
        # Check if allJobs field has been set
        if jobs_object["jobsConfig"]["errorMsg"][ii].get("allJobs") == "true":
            common_keys.append(ii)
        else:
            # If not, check value from defaultConfig section
            if jobs_object["defaultConfig"]["allJobs"] == "true":
                common_keys.append(ii)

        # Check if forceRetry field has been set
        if jobs_object["jobsConfig"]["errorMsg"][ii].get("forceRetry") == "true":
            force_retry_regex.extend(
                jobs_object["jobsConfig"]["errorMsg"][ii]["errorStr"]
            )
        else:
            # If not, check value from defaultConfig section
            if jobs_object["defaultConfig"]["forceRetry"] == "true":
                force_retry_regex.extend(
                    jobs_object["jobsConfig"]["errorMsg"][ii]["errorStr"]
                )

    # Get the error keys of the concrete job ii
    error_keys = jobs_object["jobsConfig"]["jenkinsJobs"][job_id]["errorType"][:]
    error_keys.extend(common_keys)
    error_keys = list(set(error_keys))

    error_list = append_actions(error_keys, jenkins_errors)

    return error_list, force_retry_regex


def append_actions(error_keys, jenkins_errors):
    """ Match error regex with the action to perform."""
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
    return error_list


def get_finished_builds(job_dir, running_builds):
    """Check if any build has finished."""
    return [
        build
        for build in running_builds
        if grep(
            functools.reduce(os.path.join, [job_dir, build, "build.xml"]), "<result>",
        )
    ]


def get_running_builds(job_dir):
    """Get list of new running builds that have been started after the last processed log."""
    return [
        dir.name
        for dir in os.scandir(job_dir)
        if dir.name.isdigit()
        and os.path.isfile(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"])
        )
        and not grep(
            functools.reduce(os.path.join, [job_dir, dir.name, "build.xml"]), "<result>"
        )
    ]
