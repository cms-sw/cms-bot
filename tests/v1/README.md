# Testing process_pr.py

## To replay the tests
* Run `./run_pr_tests.sh [test_name]`, will run all tests if `test_name` is not given

## To record a new test:

### Setup
* Run tests in replay mode at least once to create venv
* Create `GithubCredentials.py` in top-level directory (**not** in `tests/`) with contents:

```py
login = "<your username>"
password = ""
oauth_token = "<your oauth token>"
jwt = ""
app_id = ""
app_private_key = ""
```

* Also write oauth token in `~/.github-token`

### Recording tests

* Prepare (or update) a (cmssw) PR with desired state
* Implement a new test in `test_process_pr.py`. For most tests, only a call to `self.runTest(prId=...)` is needed.
* Run `./process-pull-request.py -n -r <repo> <prId>` to check bot behaviour 
* Run `pytest --auth_with_token --record -k test_draft_pr_opened test_process_pr.py` to record PR state and bot actions
* Check recorded actions (`PRActionData/TestProcessPr.<test name>.json`)
* Make bot actually perform actions: `./process-pull-request.py -r <repo> <prId>`