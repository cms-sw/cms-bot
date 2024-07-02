# Testing process_pr.py

## To replay the tests
* Download [Framework.py](https://github.com/PyGithub/PyGithub/blob/v1.56/tests/Framework.py) from PyGithub repo (make sure to use this exact version) and place it in `tests` folder
* Replace all `pool_size=self.pool_size` with `per_page=100` (a total of three replacements)
* Run `pytest test_process_pr.py [-k test_name] --auth_with_token`

## To record a new test:
* Download [Framework.py](https://github.com/PyGithub/PyGithub/blob/v1.56/tests/Framework.py) from PyGithub repo (make sure to use this exact version) and place it in `tests` folder
* Replace all `pool_size=self.pool_size` with `per_page=100` (a total of three replacements)
* Create `GithubCredentials.py` in top-level directory with contents:

```py
login = "<your username>"
password = ""
oauth_token = "<your oauth token>"
jwt = ""
app_id = ""
app_private_key = ""
```

* Run `pytest test_process_pr.py -k <test_name> --record --auth_with_token`
