# Introduction.

cms-bot started as a single script used to drive PR approval and grew to
be the core of the whole release engineering process for CMSSW.

# Setup

To have it working you'll need a `~/.github-token` which can access the
[cms-sw](http://github.io/cms-sw) organization.

# Release integration

-
[process-pull-request](https://github.com/cms-sw/cms-bot/blob/master/process-pull-request):
this is the script which updates the status of a CMSSW PR. It parses all the
messages associated to the specified PR and if it spots a transition (e.g. a L2
signature) it posts a message acknowledging what happended, updates the tags
etc. The state of the PR is fully obtained by parsing all the comments, so that
we do not have to maintain our own state tracking DB.
- [watchers.yaml](https://github.com/cms-sw/cms-bot/blob/master/watchers.yaml):
contains all the information required by `process-pull-requests` to notify
developers when a PR touches the packages they watch.

# Release building

- [process-build-release-request](https://github.com/cms-sw/cms-bot/blob/master/process-build-release-request)
- [release-build](): script used to build a release which has been requested
through a Github issue.
- [upload-release](): script used to upload a release to the repository. When
the job processing build requests spots a request to upload, it SSH to the
build machine which has the release and executes this script.
- [config.map](https://github.com/cms-sw/cms-bot/blob/master/config.map): semicolon separated `key=value`
pairs formatted file with release queue related information. Each line represent a release queue. In
particular `CMSDIST_TAG` is used to point to the CMSDIST tag to be used by the release building process.

# Logging

Logging happens at many different level but we are trying to unify things using
Elasticsearch for "live" data from which we dump precomputed views on a 
basis.

- [es-templates](https://github.com/cms-sw/cms-bot/tree/master/es-templates): contains the templates for the logged dataes-templates.
- [es-cleanup-indexes](https://github.com/cms-sw/cms-bot/blob/master/es-cleanup-indexes): cleanups old indexes in elasticsearch.
