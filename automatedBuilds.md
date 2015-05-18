---
title: CMS-bot
layout: default
redirect_from:
  - /cmssw/automatedBuilds.html
---


# Automated Build of Releases

The github issues can be used to build CMSSW Releases. The main idea is that an authorized user creates an issue with the name "Build \<release_name\>".
Then, cms-bot guides you through the process. 

Only authorized people can request of a release trhough a github issue. To request the build of a release ( that means that your issue is processed by cms-bot )
your username must be in the list REQUEST_BUILD_RELEASE in the [categories.py](https://github.com/cms-sw/cms-bot/blob/master/categories.py) file. 
Likewise, the build must be approved from one of the users in the list APPROVE_BUILD_RELEASE. 

if you are not authorized to request a build, cms-bot will simply ignore the issue. In this [diagram](data/AutomatedBuildOfReleases.pdf) you can see a detailed description
of the process.

Notice that there is a label for each state of the process, this is the way in which cms-bot can tell the status of a build issue.


## General Workflow

[Here](https://github.com/cms-sw/cmssw/issues/8372) you can see an example of the process.
This process is inteded to be very similar to the [manual workflow](http://cms-sw.github.io/build-release.html) and 
at any time the release manager should be able to manually continue it or solve a failure. 

- **Step 1:** Create a new issue with the name "Build \<release_name\>". Only if you are in [REQUEST_BUILD_RELEASE](https://github.com/cms-sw/cms-bot/blob/master/categories.py#L4)
  your issue will be processed. 
- **Step 2:** someone from [APPROVE_BUILD_RELEASE](https://github.com/cms-sw/cms-bot/blob/master/categories.py#L5) needs to write "+1" in a comment to start the build. When that 
  happens, the release is created in github, the cmssw tag created, and the build is queued in jenkins.
- **Step 3:** When the builds for different architectures finish sucessfully, cms-bot informs it in the conversation, it also runs some tests on the release. You can check the logs
  for the builds and the tests to decide if it is ok to be uploaded and installed. If everything is ok, you can write "upload all" in the conversation and cms-bot will start to
  upload the builds for each architecture as soon as they finish successfully. The instalation in AFS is triggered automatically after the upload finishes.
- **Step 4:** You can generate the release notes by writing "release-notes since \<previous_release\>". The workspaces used for the build in the jenkins nodes will be cleaned up
  2 days after the release notes are generated. 

**Important:** The state of the build is marked using the labels of the Github Issue. There is a main label that represents the state of the process, and a label per each architecture that indicates the particular state of that architecture. You can modify the labels of the issue to change the state of the build. For example, if the build for the architecture `slc6_amd64_gcc481` had an error, the issue will get the label *slc6_amd64_gcc481-build-error*. If you can manually fix the issue in the jenkins node, you can remove that label replace it with *slc6_amd64_gcc481-build-ok*. cms-bot will interpret it as if the build for that architecture went ok and continue with the workflow. 

## Scripts and Jenkins Jobs

- [process-build-release-request](https://github.com/cms-sw/cms-bot/blob/master/process-build-release-request): script that handles the github issue used to request the build. It orchestates the triggering of the next scripts according to the status of the build. 
  Run by [query-build-release-issues](https://cmssdt.cern.ch/jenkins/job/query-build-release-issues/)
- [build-release](https://github.com/cms-sw/cms-bot/blob/master/build-release): script used to build a release which has been requested
through a Github issue. It can also build only cmssw-tool-conf if requested. 
  Run by [build-release (jenkins)](https://cmssdt.cern.ch/jenkins/job/build-release/).
- [upload-release](https://github.com/cms-sw/cms-bot/blob/master/upload-release): script used to upload a release to the repository. Tt SSH to the
build machine which has the release and executes this script.
  Run by [upload-release (jenkins)](https://cmssdt.cern.ch/jenkins/job/upload-release/). It is triggered after the comment "upload all" is found in the issue. 
- [report-build-release-status](https://github.com/cms-sw/cms-bot/blob/master/report-build-release-status) script used   to report the status of the build.
- [release-deploy-afs](https://github.com/ktf/cms-bot/blob/master/release-deploy-afs): takes care of installing the release in afs, it is run by
[release-deploy-afs (jenkins)](https://cmssdt.cern.ch/jenkins/job/release-deploy-afs/). It is triggered automatically after the upload finished correctly. 
- [release-notes](https://github.com/cms-sw/cms-bot/blob/master/release-notes): generates the release notes for the release, is run by [release-produce-changelog](https://cmssdt.cern.ch/jenkins/job/release-produce-changelog/). 
- [cleanup-auto-build](https://github.com/cms-sw/cms-bot/blob/master/cleanup-auto-build) cleans the workspace of a build in the node where it was built. It is triggered 2 days after the release has been announced (2 days after the command to generate the release notes was written). Run by [cleanup-auto-build (jenkins)](https://cmssdt.cern.ch/jenkins/job/cleanup-auto-build/).
- [kill-build-release](https://github.com/cms-sw/cms-bot/blob/master/kill-build-release) when the build is aborted, it kills the process that was building the release. It is run by [kill-build-release (jenkins)](https://cmssdt.cern.ch/jenkins/job/kill-build-release/). It logs into the machine that is building the release, and kills the process. [build-release](https://github.com/cms-sw/cms-bot/blob/master/build-release) writes the pid in the file `$WORKSPACE/BUILD_PID`, this is used by kill-build-release to get the pid to kill.
