## Setting up Pull Requests testing for CMS user repositories
### Setup you repository
- Make a Pull Request to add your repository configuration in `cms-bot/repos/user/repository`
  - If you have `-` in your github user or repository name then replace it with `_`
- It is better to copy existing configuration and change it accordingly e.g. copy `repos/smuzaffar/SCRAM` in to `repos/user/repository`
- If you want `cmsbot` github user to update your repository/pull requests/issue (e.g. adding webhooks, setting labels etc.) then please
  - If you have a github organization then please add github user `cmsbot` in to a team with write (or admin) rights
  - If it is not a organization then please add `cmsbot` as Collaborators (under the Settings of your repository).
- Add github webhook so that bot can get notifications.
  - If you have given admin rights to `cmsbot` and set `ADD_WEB_HOOK=True` in `repos/user/repo/repo_config.py` then bot can add web-hook
  - If `cmsbot` does not have admin rights to your repository then please add yourself the github webhook (under Settings of your repository) so that bot can recognize your webhooks
    - Please disable SSL Verificaton as github does not recognize cmssdt.cern.ch certificate
    - Payload URL: https://cmssdt.cern.ch/SDT/cgi-bin/github_webhook
    - Content type: application/json
    - Secret: any password of your choice
    - Disable SSL Verification
    - Let me select individual events: Select
      - Issues, Issue comment, Pull request 
      - Pushes (for push based events)
    - Once you have created the webhook then please encrypt your secret by running `curl -d 'TOKEN=your-secret' https://cmssdt.cern.ch/SDT/cgi-bin/encrypt_github_token` and add `GITHUB_WEBHOOK_TOKEN=encrypted-token` in the `repos/user/repo/repo_config.py` file.

### Pull request Testing:
- For `user/cmssw` and `user/cmsdist` repositories , bot can run standard PR tests.
  - If you do not want to run standard cms PR tests then set `CMS_STANDARD_TESTS=False` in your `repo_config.py` file.
- For `user/non-cmssw` repository, you need to provide `repos/your_repository/run-pr-tests` script which bot can run.
  - bot will clone your repository in `$WORKSPACE/userrepo` and will merge your pull request on top of your default branch
  - A file `$WORKSPACE/changed-files.txt` will contain the list of changed file in the Pull Request
  - If you want to upload job logs (max 1G) then copy them under `$WORKSPACE/upload`
- cmsbot commands are listed here http://cms-sw.github.io/cms-bot-cmssw-cmds.html

### Push based testsing
- You can have your repository setup to trigger the tests whenever you push some changes to your repo. In this case, please make sure that github webhook for *Pushes* is active.
