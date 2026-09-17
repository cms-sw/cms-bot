#!/usr/bin/env python3

import re

KEYS_RE = "(IB_TEST_TYPE|BUILD_OPTS|CMS_BOT_BRANCH|CVMFS_INSTALL_IMAGE|DEBUG_EXTERNALS|SKIP_TESTS|REQUIRED_TEST|FORCE_FULL_IB|SLAVE_LABELS|SINGULARITY|IB_ONLY|BUILD_DAY|NO_IB|SCRAM_ARCH|RELEASE_QUEUE|BUILD_PATCH_RELEASE|PKGTOOLS_TAG|CMSDIST_TAG|RELEASE_BRANCH|ADDITIONAL_TESTS|PR_TESTS|DISABLED|ALWAYS_TAG_CMSSW|DO_STATIC_CHECKS|PROD_ARCH|ENABLE_DEBUG|PRS_TEST_CLANG|MESOS_QUEUE|DO_NOT_INSTALL|BUILD_HOUR|IB_WEB_PAGE|DOCKER_IMG)"

errors = []


def check_value(key, value):
    print("Checking", key, value)
    if key == "BUILD_OPTS":
        seen = []
        for item in value.split(","):
            iname = item.split(":", 1)[0]
            if iname in seen:
                errors.append("ERROR: Duplicate item '%s' in '%s=%s'" % (iname, key, value))
            else:
                seen.append(iname)
            if item in [
                "estats",
                "frame_pointer",
                "no-biglib",
                "no-lto",
                "no-vecgeom",
                "warnings",
            ]:
                continue
            elif re.match(r"^(cpp)\d+$", item):
                continue
            elif re.match(r"^(builders):\d+$", item):
                continue
            elif re.match(r"^(microarchs):x86-64-v\d$", item):
                continue
            elif re.match(r"^(system|without|debug):[a-zA-Z0-9_-]+(:[a-zA-Z0-9_-]+)*$", item):
                continue
            elif re.match(r"^(stdcxx):[a-zA-Z0-9_-]+@\d+(:[a-zA-Z0-9_-]+@\d+)*$", item):
                continue
            else:
                errors.append("Invalid item '%s' in '%s=%s'" % (item, key, value))
    return


if __name__ == "__main__":
    for l in open("config.map").read().split("\n"):
        if not l:
            continue
        l = l.strip(";")
        for p in l.split(";"):
            assert "=" in p
            key, value = p.split("=")
            check_value(key, value)

if errors:
    print("\n".join(errors))
    exit(1)
