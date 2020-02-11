from github import Github

def comment_gh_pr(repo, pr, msg):
      from os import environ
      gh = Github(gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip()))
      repo = gh.get_repo(repo)
      pr   = repo.get_issue(pr)
      pr.create_comment(msg)
