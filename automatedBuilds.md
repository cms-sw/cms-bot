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

## General Workflow

[Here](https://github.com/cms-sw/cmssw/issues/8372) you can see an example of the process.
This process is inteded to be very similar to the [manual workflow](http://cms-sw.github.io/build-release.html) and 
at any time the release manager should be able to manually continue it or solve a failure. 

- Step 1: Create a new issue with the name "Build \<release_name\>". Only if you are in [REQUEST_BUILD_RELEASE](https://github.com/cms-sw/cms-bot/blob/master/categories.py#L4)
  your isse will be processed. 
- Step 2: someone from [APPROVE_BUILD_RELEASE](https://github.com/cms-sw/cms-bot/blob/master/categories.py#L5) needs to write "+1" in a comment to start the build. When that 
  happens, the release is created in github, the cmssw tag created, and the build is queued in jenkins.
- Step 3: When the builds for different architectures finish sucessfully, cms-bot informs it in the conversation, it also runs some tests on the release. You can check the logs
  for the builds and the tests to decide if it is ok to be uploaded and installed. If everything is ok, you can write "upload all" in the conversation and cms-bot will start to
  upload the builds for each architecture as soon as they finish successfully.
- Step 4: You can generate the release notes by writing "release-notes since \<previous_release\>". The workspaces used for the build in the jenkins nodes will be cleaned up
  2 days after the release notes are generated. 

## Scripts and Jenkins Jobs

- [process-build-release-request](https://github.com/cms-sw/cms-bot/blob/master/process-build-release-request): script that handles the github issue used to request the build.
  Run by [query-build-release-issues](https://cmssdt.cern.ch/jenkins/job/query-build-release-issues/)
- [build-release](https://github.com/cms-sw/cms-bot/blob/master/build-release): script used to build a release which has been requested
through a Github issue.
  Run by [build-release (jenkins)](https://cmssdt.cern.ch/jenkins/job/build-release/)
- [upload-release](https://github.com/cms-sw/cms-bot/blob/master/upload-release): script used to upload a release to the repository. When
the job processing build requests spots a request to upload, it SSH to the
build machine which has the release and executes this script.
  Run by [upload-release (jenkins) ](https://cmssdt.cern.ch/jenkins/job/upload-release/)
- [report-build-release-status](https://github.com/cms-sw/cms-bot/blob/master/report-build-release-status) script used   to report the status of the build.
