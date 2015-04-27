## How can I tell which version of an external is used?

First lookup your release in [config.map](https://github.com/cms-sw/cms-bot/blob/master/config.map).

Each line contains properties of a release queue.

`CMSDIST_TAG` will tell you which CMSDIST tag / branch to lookup in:

<https://github.com/cms-sw/cmsdist>

Look up for the spec related to your external and you should find in the first
rows either a line of the kind:

    Source: <some-url>

for example:

    Source: git+https://github.com/%github_user/root.git?obj=%{branch}/%{tag}&export=%{n}-%{realversion}&output=/%{n}-%{realversion}-%{tag}.tgz

the `%{defined-variable}` gets expanded to their value, as required by rpm. In particular in many cases we have:

- `%tag`: the hash commit to be used for the external.
- `%branch`: the branch on which the commit its located.
- `github_user`: the user owning the repository to be used.
