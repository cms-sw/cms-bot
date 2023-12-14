#########################################################
# This library need to support both python3 and python2 #
# so makes sure changes work for both py2/py3
#########################################################
from __future__ import print_function
from sys import argv, version_info
from hashlib import md5
import json, sys, datetime
from time import sleep, gmtime, mktime, strptime
from _py2with3compatibility import run_cmd, urlopen, Request, urlencode
from os.path import exists, dirname, abspath, join, basename, expanduser
import re

GH_TOKENS = []
GH_USER = None
GH_TOKEN_INDEX = 0
GH_RATE_LIMIT = [5000, 5000, 3600]
GH_PAGE_RANGE = []
try:
    from github import UnknownObjectException
except:

    class UnknownObjectException(Exception):
        pass


try:
    scriptPath = dirname(abspath(__file__))
except Exception as e:
    scriptPath = dirname(abspath(argv[0]))


def format(s, **kwds):
    return s % kwds


def comment_gh_pr(gh, repo, pr, msg):
    repo = gh.get_repo(repo)
    pr = repo.get_issue(pr)
    pr.create_comment(msg)


def github_time(gh_time):
    return int(mktime(strptime(gh_time, "%Y-%m-%dT%H:%M:%SZ")))


def get_page_range():
    return GH_PAGE_RANGE[:]


def _check_rate_limits(
    rate_limit, rate_limit_max, rate_limiting_resettime, msg=True, when_slow=False, prefix=""
):
    global GH_TOKENS, GH_TOKEN_INDEX
    from calendar import timegm
    from datetime import datetime

    doSleep = 0
    rate_reset_sec = rate_limiting_resettime - timegm(gmtime()) + 5
    if msg:
        print(
            "%sAPI Rate Limit: %s/%s, Reset in %s sec i.e. at %s"
            % (
                prefix,
                rate_limit,
                rate_limit_max,
                rate_reset_sec,
                datetime.fromtimestamp(rate_limiting_resettime),
            )
        )
    if rate_limit < 100:
        doSleep = rate_reset_sec
    elif rate_limit < 200:
        doSleep = 5
    elif rate_limit < 300:
        doSleep = 2
    elif rate_limit < 500:
        doSleep = 1
    elif rate_limit < 1000:
        doSleep = 0.5
    elif rate_limit < 2000:
        doSleep = 0.25
    if rate_reset_sec < doSleep:
        doSleep = rate_reset_sec
    if when_slow:
        msg = True
    if doSleep > 0:
        tok_len = len(GH_TOKENS) - 1
        if tok_len >= 1:
            GH_TOKEN_INDEX = 0 if (GH_TOKEN_INDEX == tok_len) else GH_TOKEN_INDEX + 1
            get_rate_limits()
            if GH_TOKEN_INDEX > 0:
                return
        if msg:
            print(
                "%sSlowing down for %s sec due to api rate limits %s approching zero (reset in %s secs)"
                % (prefix, doSleep, rate_limit, rate_reset_sec)
            )
        sleep(doSleep)
    return


def check_rate_limits(msg=True, when_slow=False, prefix=""):
    _check_rate_limits(
        GH_RATE_LIMIT[0], GH_RATE_LIMIT[1], GH_RATE_LIMIT[2], msg, when_slow, prefix=prefix
    )


def api_rate_limits_repo(obj, msg=True, when_slow=False, prefix=""):
    global GH_RATE_LIMIT
    GH_RATE_LIMIT = [
        int(obj.raw_headers["x-ratelimit-remaining"]),
        int(obj.raw_headers["x-ratelimit-limit"]),
        int(obj.raw_headers["x-ratelimit-reset"]),
    ]
    check_rate_limits(msg, when_slow, prefix=prefix)


def api_rate_limits(gh, msg=True, when_slow=False, prefix=""):
    global GH_RATE_LIMIT
    gh.get_rate_limit()
    GH_RATE_LIMIT = [
        int(gh.rate_limiting[0]),
        int(gh.rate_limiting[1]),
        int(gh.rate_limiting_resettime),
    ]
    check_rate_limits(msg, when_slow, prefix=prefix)


def get_ported_PRs(repo, src_branch, des_branch):
    done_prs_id = {}
    prRe = re.compile("Automatically ported from " + src_branch + " #(\d+)\s+.*", re.MULTILINE)
    for pr in repo.get_pulls(base=des_branch):
        body = pr.body.encode("ascii", "ignore")
        if sys.version_info[0] == 3:
            body = body.decode()
        m = prRe.search(body)
        if m:
            done_prs_id[int(m.group(1))] = pr.number
            print(m.group(1), "=>", pr.number)
    return done_prs_id


def port_pr(repo, pr_num, des_branch, dryRun=False):
    pr = repo.get_pull(pr_num)
    if pr.base.ref == des_branch:
        print("Warning: Requested to make a PR to same branch", pr.base.ref)
        return False
    done_prs_id = get_ported_PRs(repo, pr.base.ref, des_branch)
    if pr_num in done_prs_id:
        print("Already ported as #", done_prs_id[pr.number])
        return True
    branch = repo.get_branch(des_branch)
    print(
        "Preparing checkout area:",
        pr_num,
        repo.full_name,
        pr.head.user.login,
        pr.head.ref,
        des_branch,
    )
    prepare_cmd = format(
        "%(cmsbot)s/prepare-repo-clone-for-port.sh %(pr)s %(pr_user)s/%(pr_branch)s %(repo)s %(des_branch)s",
        cmsbot=scriptPath,
        pr=pr_num,
        repo=repo.full_name,
        pr_user=pr.head.user.login,
        pr_branch=pr.head.ref,
        des_branch=des_branch,
    )
    err, out = run_cmd(prepare_cmd)
    print(out)
    if err:
        return False
    all_commits = set([])
    for c in pr.get_commits():
        all_commits.add(c.sha)
        git_cmd = format(
            "cd %(clone_dir)s; git cherry-pick -x %(commit)s",
            clone_dir=pr.base.repo.name,
            commit=c.sha,
        )
        err, out = run_cmd(git_cmd)
        print(out)
        if err:
            return False
    git_cmd = format(
        "cd %(clone_dir)s; git log %(des_branch)s..",
        clone_dir=pr.base.repo.name,
        des_branch=des_branch,
    )
    err, out = run_cmd(git_cmd)
    print(out)
    if err:
        return False
    last_commit = None
    new_commit = None
    new_commits = {}
    for line in out.split("\n"):
        m = re.match("^commit\s+([0-9a-f]+)$", line)
        if m:
            print("New commit:", m.group(1), last_commit)
            if last_commit:
                new_commits[new_commit] = last_commit
            new_commit = m.group(1)
            new_commits[new_commit] = None
            continue
        m = re.match("^\s*\(cherry\s+picked\s+from\s+commit\s([0-9a-f]+)\)$", line)
        if m:
            print("found commit", m.group(1))
            last_commit = m.group(1)
    if last_commit:
        new_commits[new_commit] = last_commit
    if pr.commits != len(new_commits):
        print(
            "Error: PR has ",
            pr.commits,
            " commits while we only found ",
            len(new_commits),
            ":",
            new_commits,
        )
    for c in new_commits:
        all_commits.remove(new_commits[c])
    if all_commits:
        print("Something went wrong: Following commists not cherry-picked", all_commits)
        return False
    git_cmd = format(
        "cd %(clone_dir)s; git rev-parse --abbrev-ref HEAD", clone_dir=pr.base.repo.name
    )
    err, out = run_cmd(git_cmd)
    print(out)
    if err or not out.startswith("port-" + str(pr_num) + "-"):
        return False
    new_branch = out
    git_cmd = format(
        "cd %(clone_dir)s; git push origin %(new_branch)s",
        clone_dir=pr.base.repo.name,
        new_branch=new_branch,
    )
    if not dryRun:
        err, out = run_cmd(git_cmd)
        print(out)
        if err:
            return False
    else:
        print("DryRun: should have push %s branch" % new_branch)
    from cms_static import GH_CMSSW_ORGANIZATION

    newHead = "%s:%s" % (GH_CMSSW_ORGANIZATION, new_branch)
    newBody = (
        pr.body
        + "\nAutomatically ported from "
        + pr.base.ref
        + " #%s (original by @%s)." % (pr_num, str(pr.head.user.login))
    )
    print(newHead)
    print(newBody)
    if not dryRun:
        newPR = repo.create_pull(title=pr.title, body=newBody, base=des_branch, head=newHead)
    else:
        print("DryRun: should have created Pull Request for %s using %s" % (des_branch, newHead))
    print("Every thing looks good")
    git_cmd = format(
        "cd %(clone_dir)s; git branch -d %(new_branch)s",
        clone_dir=pr.base.repo.name,
        new_branch=new_branch,
    )
    err, out = run_cmd(git_cmd)
    print("Local branch %s deleted" % new_branch)
    return True


def prs2relnotes(notes, ref_repo=""):
    new_notes = {}
    for pr_num in notes:
        new_notes[pr_num] = format(
            "- %(ref_repo)s#%(pull_request)s from @%(author)s: %(title)s",
            ref_repo=ref_repo,
            pull_request=pr_num,
            author=notes[pr_num]["author"],
            title=notes[pr_num]["title"],
        )
    return new_notes


def cache_invalid_pr(pr_id, cache):
    if not "invalid_prs" in cache:
        cache["invalid_prs"] = []
    cache["invalid_prs"].append(pr_id)
    cache["dirty"] = True


def fill_notes_description(notes, repo_name, cmsprs, cache={}):
    new_notes = {}
    for log_line in notes.splitlines():
        print("Log:", log_line)
        items = log_line.split(" ")
        author = items[1]
        pr_number = items[0]
        if cache and (pr_number in cache):
            new_notes[pr_number] = cache[pr_number]["notes"]
            print("Read from cache ", pr_number)
            continue
        parent_hash = items.pop()
        pr_hash_id = pr_number + ":" + parent_hash
        if "invalid_prs" in cache and pr_hash_id in cache["invalid_prs"]:
            continue
        print("Checking ", pr_number, author, parent_hash)
        try:
            pr_md5 = md5((pr_number + "\n").encode()).hexdigest()
            pr_cache = join(cmsprs, repo_name, pr_md5[0:2], pr_md5[2:] + ".json")
            print("Checking cached file: " + pr_cache)
            if not exists(pr_cache):
                print("  Chache does not exists: ", pr_cache)
                cache_invalid_pr(pr_hash_id, cache)
                continue
            pr = json.load(open(pr_cache))
            if not "auther_sha" in pr:
                print("  Invalid/Indirect PR", pr)
                cache_invalid_pr(pr_hash_id, cache)
                continue
            ok = True
            if pr["author"] != author:
                print("  Author mismatch:", pr["author"])
                ok = False
            if pr["auther_sha"] != parent_hash:
                print("  sha mismatch:", pr["auther_sha"])
                ok = False
            if not ok:
                print("  Invalid/Indirect PR")
                cache_invalid_pr(pr_hash_id, cache)
                continue
            new_notes[pr_number] = {
                "author": author,
                "title": pr["title"],
                "user_ref": pr["auther_ref"],
                "hash": parent_hash,
                "branch": pr["branch"],
            }
            if not pr_number in cache:
                cache[pr_number] = {}
                cache[pr_number]["notes"] = new_notes[pr_number]
                cache[pr_number]["pr"] = pr
                cache["dirty"] = True
        except UnknownObjectException as e:
            print("ERR:", e)
            cache_invalid_pr(pr_hash_id, cache)
            continue
    return new_notes


def get_merge_prs(prev_tag, this_tag, git_dir, cmsprs, cache={}, repo_name=None):
    print("Getting merged Pull Requests b/w", prev_tag, this_tag)
    cmd = format(
        "GIT_DIR=%(git_dir)s"
        " git log --graph --merges --pretty='%%s: %%P' %(previous)s..%(release)s | "
        " grep ' Merge pull request #[1-9][0-9]* from ' | "
        " sed 's|^.* Merge pull request #||' | "
        " sed 's|Dr15Jones:clangRecoParticleFlowPFProducer:|Dr15Jones/clangRecoParticleFlowPFProducer:|' | "
        " sed 's|/[^:]*:||;s|from ||'",
        git_dir=git_dir,
        previous=prev_tag,
        release=this_tag,
    )
    error, notes = run_cmd(cmd)
    print("Getting Merged Commits:", cmd)
    print(notes)
    if error:
        print("Error while getting release notes.")
        print(notes)
        exit(1)
    if not repo_name:
        repo_name = basename(git_dir[:-4])
    return fill_notes_description(notes, "cms-sw/" + repo_name, cmsprs, cache)


def save_prs_cache(cache, cache_file):
    if cache["dirty"]:
        del cache["dirty"]
        with open(cache_file, "w") as out_json:
            json.dump(cache, out_json, indent=2, sort_keys=True)
            out_json.close()
        cache["dirty"] = False


def read_prs_cache(cache_file):
    cache = {}
    if exists(cache_file):
        with open(cache_file) as json_file:
            cache = json.loads(json_file.read())
            json_file.close()
    cache["dirty"] = False
    return cache


def get_ref_commit(repo, ref):
    for n in ["tags", "heads"]:
        error, out = run_cmd(
            "curl -s -L https://api.github.com/repos/%s/git/refs/%s/%s" % (repo, n, ref)
        )
        if not error:
            info = json.loads(out)
            if "object" in info:
                return info["object"]["sha"]
    print("Error: Unable to get sha for %s" % ref)
    return None


def get_commit_info(repo, commit):
    error, out = run_cmd(
        "curl -s -L https://api.github.com/repos/%s/git/commits/%s" % (repo, commit)
    )
    if error:
        tag = "X (tag is undefined)"  # TODO tag is undefined
        print("Error, unable to get sha for tag %s" % tag)
        return {}
    commit_info = json.loads(out)
    if "sha" in commit_info:
        return commit_info
    return {}


def create_team(org, team, description):
    params = {"name": team, "description": description, "privacy": "closed"}
    return github_api("/orgs/%s/teams" % org, params=params, method="POST")


def get_pending_members(org):
    return github_api("/orgs/%s/invitations" % org, method="GET")


def get_failed_pending_members(org):
    return github_api("/orgs/%s/failed_invitations" % org, method="GET")


def get_delete_pending_members(org, invitation_id):
    return github_api("/orgs/%s/invitations/%s" % (org, invitation_id), method="DELETE", raw=True)


def get_organization_members(org, role="all", filter="all"):
    return github_api(
        "/orgs/%s/members" % org, params={"role": role, "filter": filter}, method="GET"
    )


def get_organization_repositores(org):
    return github_api("/orgs/%s/repos" % org, method="GET")


def get_repository(repo):
    return github_api("/repos/%s" % repo, method="GET")


def add_organization_member(org, member, role="member"):
    return github_api(
        "/orgs/%s/memberships/%s" % (org, member), params={"role": role}, method="PUT"
    )


def invite_organization_member(org, member, role="direct_member"):
    return github_api(
        "/orgs/%s/invitations" % org, params={"role": role, "invitee_id": member}, method="POST"
    )


def edit_pr(repo, pr_num, title=None, body=None, state=None, base=None):
    get_gh_token(repo)
    params = {}
    if title:
        params["title"] = title
    if body:
        params["body"] = body
    if base:
        params["base"] = base
    if state:
        params["state"] = state
    return github_api(uri="/repos/%s/pulls/%s" % (repo, pr_num), params=params, method="PATCH")


def create_issue_comment(repo, issue_num, body):
    get_gh_token(repo)
    return github_api(
        uri="/repos/%s/issues/%s/comments" % (repo, issue_num), params={"body": body}
    )


def get_issue_labels(repo, issue_num):
    get_gh_token(repo)
    return github_api(uri="/repos/%s/issues/%s/labels" % (repo, issue_num), method="GET")


def add_issue_labels(repo, issue_num, labels=[]):
    get_gh_token(repo)
    return github_api(
        uri="/repos/%s/issues/%s/labels" % (repo, issue_num),
        params={"labels": labels},
        method="POST",
    )


def set_issue_labels(repo, issue_num, labels=[]):
    get_gh_token(repo)
    return github_api(
        uri="/repos/%s/issues/%s/labels" % (repo, issue_num),
        params={"labels": labels},
        method="PUT",
    )


def remove_issue_labels_all(repo, issue_num):
    get_gh_token(repo)
    return github_api(
        uri="/repos/%s/issues/%s/labels" % (repo, issue_num), method="DELETE", status=[204]
    )


def remove_issue_label(repo, issue_num, label):
    get_gh_token(repo)
    return github_api(
        uri="/repos/%s/issues/%s/labels/%s" % (repo, issue_num, label), method="DELETE"
    )


def get_rate_limits():
    return github_api(uri="/rate_limit", method="GET")


def merge_dicts(old, new):
    for k, v in new.items():
        if k not in old:
            old[k] = new[k]
            continue

        if isinstance(v, dict):
            old[k] = merge_dicts(old[k], new[k])
            continue

        if isinstance(v, list):
            old[k].extend(v)
            continue

        if old[k] != new[k]:
            raise RuntimeError(
                "Unable to merge dictionaries: value for key {0} differs. ".format(k)
                + "Old {0} {1}, new {2}, {3}".format(old[k], type(old[k]), new[k], type(new[k]))
            )

    return old


def github_api(
    uri,
    params=None,
    method="POST",
    headers=None,
    page=1,
    raw=False,
    per_page=100,
    last_page=False,
    all_pages=True,
    max_pages=-1,
    status=None,
    merge_dict=False,
):
    if status is None:
        status = []

    check_rate_limits(msg=False)

    global GH_RATE_LIMIT, GH_PAGE_RANGE
    if max_pages > 0 and page > max_pages:  # noqa for readability
        return "[]" if raw else []
    if not params:
        params = {}
    if not headers:
        headers = {}
    url = "https://api.github.com%s" % uri
    data = ""
    if per_page and ("per_page" not in params) and (not method in ["POST", "PATCH", "PUT"]):
        params["per_page"] = per_page
    if method == "GET":
        if params:
            url = url + "?" + urlencode(params)
    elif method in ["POST", "PATCH", "PUT"]:
        data = json.dumps(params)
    if version_info[0] == 3:
        data = data.encode("utf-8")
    if page > 1:
        if not "?" in url:
            url = url + "?"
        else:
            url = url + "&"
        url = url + "page=%s" % page
    headers["Authorization"] = "token " + get_gh_token()
    request = Request(url, data=data, headers=headers)
    request.get_method = lambda: method
    response = urlopen(request)
    if page <= 1:
        GH_PAGE_RANGE = []
    try:
        GH_RATE_LIMIT = [
            int(response.headers["X-RateLimit-Remaining"]),
            int(response.headers["X-RateLimit-Limit"]),
            int(response.headers["X-Ratelimit-Reset"]),
        ]
    except Exception as e:
        print("ERROR:", e)
    if (page <= 1) and (method == "GET"):
        link = response.headers.get("Link")
        if link:
            pages = []
            for x in link.split(" "):
                m = re.match("^.*[?&]page=([1-9][0-9]*).*$", x)
                if m:
                    pages.append(int(m.group(1)))
            if len(pages) == 2:
                GH_PAGE_RANGE += range(pages[0], pages[1] + 1)
            elif len(pages) == 1:
                GH_PAGE_RANGE += pages
    cont = response.read()
    if status:
        return response.status in status
    if raw:
        return cont
    data = json.loads(cont)
    if GH_PAGE_RANGE and all_pages:
        if last_page:
            return github_api(
                uri,
                params,
                method,
                headers,
                GH_PAGE_RANGE[-1],
                raw=False,
                per_page=per_page,
                all_pages=False,
            )
        for page in GH_PAGE_RANGE:
            if max_pages > 0 and page > max_pages:  # noqa for readability
                break
            new_data = github_api(
                uri, params, method, headers, page, raw=raw, per_page=per_page, all_pages=False
            )
            if merge_dict:
                data = merge_dicts(data, new_data)
            else:
                data += new_data
    return data


def get_pull_requests(gh_repo, branch=None, status="open"):
    """
    Get all pull request for the current branch of the repo
    :return:
    """
    params = {"state": status, "sort": "created", "direction": "asc"}
    if branch:
        params["base"] = branch
    pulls = gh_repo.get_pulls(**params)
    return pulls


def get_changed_files(pulls):
    """
    Returns union of changed file names on PR
    """
    rez = set()
    for pr in pulls:
        for f in pr.get_files():
            rez.add(f.filename)
    return sorted(rez)


def pr_get_changed_files(pr):
    rez = []
    for f in pr.get_files():
        rez.append(f.filename)
        try:
            if f.previous_filename:
                rez.append(f.previous_filename)
        except:
            pass
    return rez


def get_commit(repository, commit_sha):
    return github_api(
        "/repos/{0}/commits/{1}".format(repository, commit_sha), method="GET", merge_dict=True
    )


def get_unix_time(data_obj):
    return data_obj.strftime("%s")


def get_gh_token(repository=None, token_file=None):
    global GH_TOKENS, GH_TOKEN_INDEX
    if not GH_TOKENS:
        GH_TOKEN_INDEX = 0
        if not token_file:
            if repository:
                repo_dir = join(scriptPath, "repos", repository.replace("-", "_"))
                if exists(join(repo_dir, "repo_config.py")):
                    sys.path.insert(0, repo_dir)
            import repo_config

            token_file = expanduser(repo_config.GH_TOKEN)
        try:
            with open(token_file) as ref:
                for tok in [t.strip() for t in ref.readlines()]:
                    if not tok:
                        continue
                    GH_TOKENS.append(tok)
        except:
            GH_TOKENS = [""]
    return GH_TOKENS[GH_TOKEN_INDEX]


def set_gh_user(user):
    global GH_USER
    GH_USER = user


def get_combined_statuses(commit, repository):
    get_gh_token(repository)
    return github_api("/repos/%s/commits/%s/status" % (repository, commit), method="GET")


def get_pr_commits(pr, repository, per_page=None, last_page=False):
    get_gh_token(repository)
    return github_api(
        "/repos/%s/pulls/%s/commits" % (repository, pr),
        method="GET",
        per_page=per_page,
        last_page=last_page,
    )


def get_pr_latest_commit(pr, repository):
    get_gh_token(repository)
    return str(get_pr_commits(pr, repository, per_page=1, last_page=True)[-1]["sha"])


def set_comment_emoji(comment_id, repository, emoji="+1", reset_other=True):
    cur_emoji = None
    if reset_other:
        for e in get_comment_emojis(comment_id, repository):
            login = e["user"]["login"].encode("ascii", "ignore")
            if sys.version_info[0] == 3:
                login = login.decode()
            if login == GH_USER:
                if e["content"] != emoji:
                    delete_comment_emoji(e["id"], comment_id, repository)
                else:
                    cur_emoji = e
    if cur_emoji:
        return cur_emoji
    get_gh_token(repository)
    params = {"content": emoji}
    return github_api(
        "/repos/%s/issues/comments/%s/reactions" % (repository, comment_id), params=params
    )


def get_repository_issues(
    repository, params={"sort": "updated", "state": "all"}, page=1, all_pages=False
):
    get_gh_token(repository)
    return github_api(
        "/repos/%s/issues" % repository,
        method="GET",
        params=params,
        page=page,
        all_pages=all_pages,
    )


def get_issue_comments(repository, issue_num):
    get_gh_token(repository)
    return github_api("/repos/%s/issues/%s/comments" % (repository, issue_num), method="GET")


def get_issue(repository, issue_num):
    get_gh_token(repository)
    return github_api("/repos/%s/issues/%s" % (repository, issue_num), method="GET")


def get_releases(repository, params={"sort": "updated"}, page=1, all_pages=False):
    get_gh_token(repository)
    return github_api(
        "/repos/%s/releases" % repository,
        method="GET",
        params=params,
        page=page,
        all_pages=all_pages,
    )


def get_release_by_tag(repository, tag):
    get_gh_token(repository)
    return github_api("/repos/%s/releases/tags/%s" % (repository, tag), method="GET")


def get_comment_emojis(comment_id, repository):
    get_gh_token(repository)
    return github_api(
        "/repos/%s/issues/comments/%s/reactions" % (repository, comment_id), method="GET"
    )


def delete_comment_emoji(emoji_id, comment_id, repository):
    get_gh_token(repository)
    return github_api(
        "/repos/%s/issues/comments/%s/reactions/%s" % (repository, comment_id, emoji_id),
        method="DELETE",
        raw=True,
    )


def get_git_tree(sha, repository):
    get_gh_token(repository)
    return github_api("/repos/%s/git/trees/%s" % (repository, sha), method="GET")


def mark_commit_status(
    commit,
    repository,
    context="default",
    state="pending",
    url="",
    description="Test started",
    reset=False,
):
    get_gh_token(repository)
    params = {"state": state, "target_url": url, "description": description, "context": context}
    github_api("/repos/%s/statuses/%s" % (repository, commit), params=params)
    if reset:
        statuses = get_combined_statuses(commit, repository)
        if "statuses" not in statuses:
            return
        params = {
            "state": "success",
            "target_url": "",
            "description": "Not yet started or might not rerun",
        }
        for s in statuses["statuses"]:
            if s["context"].startswith(context + "/"):
                params["context"] = s["context"]
                github_api("/repos/%s/statuses/%s" % (repository, commit), params=params)
    return


def get_branch(repository, branch_name):
    get_gh_token(repository)
    data = github_api("/repos/%s/branches/%s" % (repository, branch_name), method="GET")
    return data


def get_git_tag(repository, tag_name):
    get_gh_token(repository)
    data = github_api("/repos/%s/git/ref/tags/%s" % (repository, tag_name), method="GET")
    return data


def create_git_tag(repository, tag_name, commit_sha):
    get_gh_token(repository)
    params = {"ref": "refs/tags/%s" % tag_name, "sha": commit_sha}
    return github_api("/repos/%s/git/refs" % repository, method="POST", params=params)


def get_commit_tags(repository, commit_sha, all_tags=False):
    get_gh_token(repository)
    res = []
    data = github_api("/repos/%s/tags" % repository, all_pages=all_tags, method="GET")
    for tag in data:
        if tag["commit"]["sha"] == commit_sha:
            res.append(tag["name"])

    return res


def get_org_packages(org, package_type="container", visibility=None, token_file=None):
    get_gh_token(token_file=token_file)
    params = {"package_type": package_type}
    if visibility:
        params["visibility"] = visibility
    return github_api(
        "/orgs/%s/packages" % org,
        method="GET",
        params=params,
        all_pages=True,
    )


def get_org_package(org, package, package_type="container", token_file=None):
    get_gh_token(token_file=token_file)
    return github_api(
        "/orgs/%s/packages/%s/%s" % (org, package_type, package), method="GET", all_pages=True
    )


def get_org_package_versions(org, package, package_type="container", token_file=None):
    get_gh_token(token_file=token_file)
    return github_api(
        "/orgs/%s/packages/%s/%s/versions" % (org, package_type, package),
        method="GET",
        all_pages=True,
    )


def get_org_package_version(org, package, version_id, package_type="container", token_file=None):
    get_gh_token(token_file=token_file)
    return github_api(
        "/orgs/%s/packages/%s/%s/versions/%s" % (org, package_type, package, version_id),
        method="GET",
    )


def get_commits(repository, branch, until, per_page=1):
    get_gh_token(repository)
    if isinstance(until, datetime.datetime):
        until = until.replace(microsecond=0).isoformat() + "Z"

    data = github_api(
        "/repos/%s/commits" % repository,
        method="GET",
        params={"sha": branch, "until": until},
        per_page=per_page,
        all_pages=False,
    )

    return data


def find_tags(repository, name):
    get_gh_token(repository)
    data = github_api("/repos/%s/git/matching-refs/tags/%s" % (repository, name), method="GET")

    return data


def get_pr(repository, pr_id):
    data = github_api("/repos/%s/pulls/%s" % (repository, pr_id), method="GET")

    return data


def get_last_commit(pr):
    commits_ = get_pr_commits_reversed(pr)
    if commits_:
        return commits_[-1]
    else:
        return None


def get_pr_commits_reversed(pr):
    """
    :param pr:
    :return: PaginatedList[Commit] | List[Commit]
    """
    try:
        # This requires at least PyGithub 1.23.0. Making it optional for the moment.
        return pr.get_commits().reversed
    except:  # noqa
        # This seems to fail for more than 250 commits. Not sure if the
        # problem is github itself or the bindings.
        try:
            return reversed(list(pr.get_commits()))
        except IndexError:
            print("Index error: May be PR with no commits")
    return []
