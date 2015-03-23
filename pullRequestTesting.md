---
title: Pull Tequest Testing
layout: default
redirect_from:
  - /cmssw/pullRequestTesting.html
---


# Pull Request Testing

cms-bot can run the following tests on a pull request:

  - Compilation
  - Unit Tests
  - Relvals
  - Static analyser checks
  - DQM Tests
  - Clang Compilation

## Main Scripts

  - [run-pr-tests](https://github.com/cms-sw/cms-bot/blob/master/run-pr-tests) is the script that runs the tests on the pull requests.
    It is run by [ib-any-integration](https://cmssdt.cern.ch/jenkins/job/ib-any-integration)
  - [report-pull-request-results](https://github.com/cms-sw/cms-bot/blob/master/report-pull-request-results) is the script that is used
    to report the results of the tests.

## Automatic triggering

  - [get-pr-branch](https://github.com/cms-sw/cms-bot/blob/master/get-pr-branch): script that prints tha branch to which a pull request
    was created.
  - [pr-schedule-tests](https://github.com/cms-sw/cms-bot/blob/master/pr-schedule-tests): script that sets the parameters to trigger
    [ib-any-integration](https://cmssdt.cern.ch/jenkins/job/ib-any-integration) depending on [get-pr-branch](https://github.com/cms-sw/cms-bot/blob/master/get-pr-branch) 
    and [config.map](https://github.com/cms-sw/cms-bot/blob/master/config.map). It is run by [ib-schedule-pr-tests](https://cmssdt.cern.ch/jenkins/job/ib-schedule-pr-tests)
  - [queue-new-prs](https://github.com/cms-sw/cms-bot/blob/master/queue-new-prs) is run by [queue-new-prs (jenkins)](https://cmssdt.cern.ch/jenkins/job/queue-new-prs/), it uses 
    [query-new-pull-requests](https://github.com/cms-sw/cms-bot/blob/master/query-new-pull-requests) to query the latest pull requests, it then uses the result of 
    [auto-trigger-pr](https://github.com/cms-sw/cms-bot/blob/master/auto-trigger-pr) to decide if the tests for the pull request can be triggered automatically.
    The tests for a pull request are automatically triggered if the following conditions are met:
      - There is at least 1 signature.
      - The tests are pending.
      - It is not already being tested.

