# Testing process_pr.py

## To replay the tests
* Run `./run_pr_tests.sh [test_name]`, will run all tests if `test_name` is not given

## To record a new test:
* Create `GithubCredentials.py` in top-level directory with contents:

```py
login = "<your username>"
password = ""
oauth_token = "<your oauth token>"
jwt = ""
app_id = ""
app_private_key = ""
```

* Run `./run_pr_tests.sh --record test_name`
