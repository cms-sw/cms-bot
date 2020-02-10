from github import Github

def comment_gh_pr(repo, pr, msg):
      from os import environ
      gh = Github(login_or_token=environ['GITHUBTOKEN'], retry=3)
      repo = gh.get_repo(repo)
      pr   = repo.get_issue(pr)
      pr.create_comment(msg)
