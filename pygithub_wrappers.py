import sys

import github

dryRun = False
actions = []
extra_data = ""

if "pytest" not in sys.modules:
    testMode = False
else:
    testMode = True

    github__issuecomment__edit = github.IssueComment.IssueComment.edit

    def comment__edit(self, body):
        actions.append({"type": "edit-comment", "data": body})
        if dryRun:
            print("DRY RUN: Updating existing comment with text")
            print(body.encode("ascii", "ignore").decode())
        else:
            return github__issuecomment__edit(self, body)

    github.IssueComment.IssueComment.edit = comment__edit

    github__issue__create_comment = github.Issue.Issue.create_comment

    def issue__create_comment(self, body):
        actions.append({"type": "create-comment", "data": body})
        if dryRun:
            print("DRY RUN: Creating comment with text")
            print(body.encode("ascii", "ignore").decode())
        else:
            github__issue__create_comment(self, body)

    github.Issue.Issue.create_comment = issue__create_comment

    github__commit__create_status = github.Commit.Commit.create_status

    def commit__create_status(self, state, target_url=None, description=None, context=None):
        actions.append(
            {
                "type": "status",
                "data": {
                    "commit": commit.sha,
                    "state": state,
                    "target_url": target_url,
                    "description": description,
                    "context": context,
                },
            }
        )

        if target_url is None:
            target_url = github.GithubObject.NotSet

        if description is None:
            description = github.GithubObject.NotSet

        if context is None:
            context = github.GithubObject.NotSet

        if not dryRun:
            github__commit__create_status.create_status(
                self, state, target_url=target_url, description=description, context=context
            )
        else:
            print(
                "DRY RUN: set commit status state={0}, target_url={1}, description={2}, context={3}".format(
                    state, target_url, description, context
                )
            )
