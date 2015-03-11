---
title: CMS-bot
layout: default
redirect_from:
  - /cmssw/
  - /cmssw/automatedBuilds.html
---


# Automated Build of Releases

The github issues can be used to build CMSSW Releases. The main idea is that an authorized user creates an issue with the name "Build \<release_name\>".
Then, cms-bot guides you through the process. 

Only authorized people can request of a release trhough a github issue. To request the build of a release ( that means that your issue is processed by cms-bot )
your username must be in the list REQUEST_BUILD_RELEASE in the [categories.py](https://github.com/cms-sw/cms-bot/blob/master/categories.py) file. 
Likewise, the build must be approved from one of the users in the list APPROVE_BUILD_RELEASE. 

if you are not authorized to request a build, cms-bot will simply ignore the issue. In this [diagram](https://docs.google.com/drawings/d/1H7Xsa-KXnsX6ZSQrskKrJjLbGPteAMHYuyMeAF2vjC8/edit?usp=sharing) you can see a detailed description
of the process. 

