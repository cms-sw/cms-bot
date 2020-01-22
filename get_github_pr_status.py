#!/usr/bin/env python
from __future__ import print_function
from github import Github
from optparse import OptionParser
import repo_config
from os.path import expanduser
from urllib2 import urlopen
from json import loads, dumps

def add_status_for_pr(gh_pr_obj=None, context='default', state='pending',
                      description='empty description', target_url='http://www.example.com'):
    commits = gh_pr_obj.get_commits()
    for comm in commits: comm_sha = comm.sha  # don't know why, but otherwise the commits list gets out of range
    last_commit = commits[-1]
    last_commit.create_status(state=state, target_url=target_url, description=description, context=context)

def get_combined_statuses_for_pr(gh_pr_obj=None):
    commits = gh_pr_obj.get_commits()
    for comm in commits: comm_sha = comm.sha
    last_commit = commits[-1]
    return last_commit.get_combined_status()

def get_overall_status_state(gh_pr_obj=None, overall_status_context_name='overall'):
    status_list = get_combined_statuses_for_pr(gh_pr_obj)
    #skip the overall status
    filtered_list = [sts for sts in status_list.statuses if sts.context != overall_status_context_name]
    states = [i.state for i in filtered_list]
    if 'failed' or 'error' in states:
        return 'failed'
    if 'pending' in states in states:
        return 'pending'
    else:
        return "success"

if __name__ == "__main__":
    #init
    parser = OptionParser(usage="%prog <cms-repo> <pull-request-id>")
    parser.add_option("-r", "--repo", dest="gh_repo_name", help="Github dist repositoy name e.g. cms-sw/cmsdist.",
                    type=str, default='')
    parser.add_option("-p", "--pull-request", dest="pull_request", help="Pull request number",
                    type=str, default=None)
    opts, args = parser.parse_args()
    gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
    pr_object = gh.get_repo(opts.gh_repo_name).get_pull(int(opts.pull_request))
    # example from here
    cs_list = get_combined_statuses_for_pr(pr_object)
    print("list size: ", len(cs_list.statuses))

    for i in cs_list.statuses:
        print("context: ", i.context, " state: ", i.state)

    #add_status_for_pr(gh_pr_obj=pr_object, context="overall", state="pending",
    #                          description="overall status description", target_url="http://www.example.com")
