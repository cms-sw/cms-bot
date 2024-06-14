#!/usr/bin/env python3
import os
import sys

import yaml

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


# Validate the schema of watchers.


def main():
    KEY_RE = "^[^@]+"
    VALUE_RE = "[A-Za-z0-0.*+]"

    watchers_file = os.path.dirname(os.path.dirname(__file__)) + "/watchers.yaml"

    w = yaml.load(open(watchers_file, "r"), Loader=Loader)
    assert type(w) == dict
    for key, value in w.items():
        assert type(key) == str
        assert re.match(KEY_RE, key)
        assert type(value) == list
        for x in value:
            assert type(x) == str
            assert re.match(VALUE_RE, x)

    assert CMSSW_CATEGORIES
    assert type(CMSSW_CATEGORIES) == dict

    PACKAGE_RE = "^([A-Z][0-9A-Za-z]*(/[a-zA-Z][0-9A-Za-z]*|)|.gitignore|pull_request_template.md|.clang-[^/]+)$"

    for key, value in CMSSW_CATEGORIES.items():
        assert type(key) == str
        assert type(value) == list
        if len(value) == 0:
            continue
        if key == "externals":
            assert len(value) > 0
            continue
        for p in value:
            print("checking", p)
            assert type(p) == str
            assert re.match(PACKAGE_RE, p)

    if os.path.exists("super-users.yaml"):
        w = yaml.load(open("super-users.yaml", "r"), Loader=Loader)
        assert type(w) == list
        for p in w:
            assert type(p) == str
            assert re.match(KEY_RE, p)

    print("Finished with success")


if __name__ == "__main__":
    #
    sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

    from releases import *
    from categories import *

    main()
