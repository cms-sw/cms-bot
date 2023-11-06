#!/usr/bin/env python

import re

KEYS_RE = "(CMS_BOT_BRANCH|CVMFS_INSTALL_IMAGE|DEBUG_EXTERNALS|SKIP_TESTS|REQUIRED_TEST|FORCE_FULL_IB|SLAVE_LABELS|SINGULARITY|IB_ONLY|BUILD_DAY|NO_IB|SCRAM_ARCH|RELEASE_QUEUE|BUILD_PATCH_RELEASE|PKGTOOLS_TAG|CMSDIST_TAG|RELEASE_BRANCH|ADDITIONAL_TESTS|PR_TESTS|DISABLED|ALWAYS_TAG_CMSSW|DO_STATIC_CHECKS|PROD_ARCH|ENABLE_DEBUG|PRS_TEST_CLANG|MESOS_QUEUE|DO_NOT_INSTALL|BUILD_HOUR|IB_WEB_PAGE|DOCKER_IMG|SPACK)"

if __name__ == "__main__":
    for l in open("config.map").read().split("\n"):
        if not l:
            continue
        l = l.strip(";")
        for p in l.split(";"):
            assert "=" in p
            (key, value) = p.split("=")
            assert re.match(KEYS_RE, key)
