---
title: IB Additional Tests
layout: default
redirect_from:
  - /cmssw/IBAdditionalTests.html
---


# IB Additional Tests

After the IB finishes building and it is installed, the jenkins job is promoted.
When the promotion happens, [schedule-additional-tests](https://github.com/cms-sw/cms-bot/blob/master/schedule-additional-tests)
([schedule-additional-tests](https://cmssdt.cern.ch/jenkins/job/schedule-additional-tests) in jenkins)
is run. 

It reads [config.map](https://github.com/cms-sw/cms-bot/blob/master/config.map)
and triggers additional tests depending on the value of `ADDITIONAL_TESTS`,
if the variable exists.

Currently, the tests that can be run are:

 - [HLT-Validation](https://cmssdt.cern.ch/jenkins/job/HLT-Validation), write 'hlt' in `ADDITIONAL_TESTS`.
 - [Baseline for comparisons](https://cmssdt.cern.ch/jenkins/job/baseline-ib-results), write 'baseline' in `ADDITIONAL_TESTS`.
   For more information see [Pull Request Comparisons](pullRequestComparisons.html).
 - [DQM Checks](https://cmssdt.cern.ch/jenkins/job/ib-dqm-checks), write 'dqm' in `ADDITIONAL_TESTS`.
 - [Static Analyzer](https://cmssdt.cern.ch/jenkins/job/ib-static-checks/), write 'static-checks' in `ADDITIONAL_TESTS`.
