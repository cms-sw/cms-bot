#!/usr/bin/env python3
"""
Returns top commit of a PR (mostly used to comments)
"""
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
from socket import setdefaulttimeout

import urllib3

from github_utils import api_rate_limits, get_pr_commits, get_pr_latest_commit, get_gh_token

setdefaulttimeout(120)
import sys

SCRIPT_DIR = dirname(abspath(sys.argv[0]))

from github.Requester import Requester
from github import Github
from github.MainClass import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_PER_PAGE


class DebugRequester(Requester):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._Requester__log = self.__log

    def __log(self, verb, url, requestHeaders, input, status, responseHeaders, output) -> None:
        print(
            "%s %s://%s%s ==> %i"
            % (
                verb,
                self._Requester__scheme,
                self._Requester__hostname,
                url,
                status,
            ),
            file=sys.stderr,
        )


class DebugGithub(Github):
    def __init__(
        self,
        login_or_token=None,
        password=None,
        jwt=None,
        base_url=DEFAULT_BASE_URL,
        timeout=DEFAULT_TIMEOUT,
        client_id=None,
        client_secret=None,
        user_agent="PyGithub/Python",
        per_page=DEFAULT_PER_PAGE,
        verify=True,
        retry=None,
    ):
        """
        :param login_or_token: string
        :param password: string
        :param base_url: string
        :param timeout: integer
        :param client_id: string
        :param client_secret: string
        :param user_agent: string
        :param per_page: int
        :param verify: boolean or string
        :param retry: int or urllib3.util.retry.Retry object
        """

        assert login_or_token is None or isinstance(login_or_token, str), login_or_token
        assert password is None or isinstance(password, str), password
        assert jwt is None or isinstance(jwt, str), jwt
        assert isinstance(base_url, str), base_url
        assert isinstance(timeout, int), timeout
        assert client_id is None or isinstance(client_id, str), client_id
        assert client_secret is None or isinstance(client_secret, str), client_secret
        assert user_agent is None or isinstance(user_agent, str), user_agent
        assert retry is None or isinstance(retry, (int)) or isinstance(retry, (urllib3.util.Retry))
        self.__requester = DebugRequester(
            login_or_token,
            password,
            jwt,
            base_url,
            timeout,
            client_id,
            client_secret,
            user_agent,
            per_page,
            verify,
            retry,
        )

        self._Github__requester = self.__requester


if __name__ == "__main__":
    parser = OptionParser(usage="%prog <pull-request-id>")
    parser.add_option(
        "-c",
        "--commit",
        dest="commit",
        action="store_true",
        help="Get last commit of the PR",
        default=False,
    )
    parser.add_option(
        "-a",
        "--all",
        dest="all",
        action="store_true",
        help="Get all commits of the PR",
        default=False,
    )
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not modify Github",
        default=False,
    )
    parser.add_option(
        "-f",
        "--force",
        dest="force",
        action="store_true",
        help="Force process the issue/PR even if it is ignored.",
        default=False,
    )
    parser.add_option(
        "-r",
        "--repository",
        dest="repository",
        help="Github Repositoy name e.g. cms-sw/cmssw.",
        type=str,
        default="cms-sw/cmssw",
    )
    parser.add_option(
        "-d",
        "--debug",
        dest="debug",
        action="store_true",
        help="Enable logging of requests",
        default=False,
    )
    opts, args = parser.parse_args()

    if len(args) != 1:
        parser.error("Too many/few arguments")
    prId = int(args[0])  # Positional argument is "Pull request ID"
    if opts.commit:
        if opts.all:
            for c in get_pr_commits(prId, opts.repository):
                print(c["sha"])
        else:
            print(get_pr_latest_commit(args[0], opts.repository))
    else:
        repo_dir = join(SCRIPT_DIR, "repos", opts.repository.replace("-", "_"))
        if exists(repo_dir):
            sys.path.insert(0, repo_dir)
        import repo_config

        if not getattr(repo_config, "RUN_DEFAULT_CMS_BOT", True):
            sys.exit(0)
        if opts.debug:
            gh = DebugGithub(login_or_token=get_gh_token(opts.repository), per_page=100)
        else:
            gh = Github(login_or_token=get_gh_token(opts.repository), per_page=100)

        api_rate_limits(gh)
        repo = gh.get_repo(opts.repository)
        from process_pr import process_pr

        process_pr(repo_config, gh, repo, repo.get_issue(prId), opts.dryRun, force=opts.force)
        api_rate_limits(gh)
