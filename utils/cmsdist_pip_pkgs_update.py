#!/usr/bin/env python
from __future__ import print_function
import sys, re, json, os
import subprocess
from os.path import exists, join


def check_python_require(py_str, condition):
    if not condition:
        return True
    if "py3" in condition:
        return py_str.startswith("3.")
    py_version = list(map(int, py_str.split(".")))
    for cond in condition.split(","):
        m = re.match("^(.*?)([0-9].*)", cond.replace(" ", ""))
        if m:
            op = m.group(1)
            regex = False
            req = m.group(2).split(".")
            if op == "":
                op = "=="
                req.append("*")
            while req[-1] == "*":
                req.pop()
                regex = True
            if regex:
                req_str = "^" + ".".join(req) + "\..+$"
                if op == "==":
                    if not re.match(req_str, py_str):
                        return False
                elif op == "!=":
                    if re.match(req_str, py_str):
                        return False
            try:
                req = list(map(int, req))
            except:
                if "'" in req:
                    continue
                # print(py_str,"A", condition,"B",req)
                # raise
            if op == ">":
                if py_version <= req:
                    return False
            elif op == ">=":
                if py_version < req:
                    return False
            elif op == "<":
                if py_version >= req:
                    return False
            elif op == "<=":
                if py_version > req:
                    return False
    return True


def requirements_file(cmsdist):
    return join(cmsdist, "pip", "requirements.txt")


def read_requirements(cmsdist):
    print("Reading requirements ...")
    req_file = requirements_file(cmsdist)
    req_data = []
    proc = subprocess.Popen(
        'grep "^### RPM" %s/python3.spec | sed "s|^.* python3 *||"' % (cmsdist),
        stdout=subprocess.PIPE,
        shell=True,
        universal_newlines=True,
    )
    py3_version = proc.stdout.read().strip()
    print("  Python3:", py3_version)
    if exists(req_file):
        with open(req_file) as ref:
            for line in ref.readlines():
                req_data.append({"line": line.strip(), "data": {}})
                line = line.strip().replace(" ", "")
                if line.startswith("#"):
                    continue
                if "==" in line:
                    p, v = line.split("==", 1)
                    req_data[-1]["data"]["name"] = p
                    req_data[-1]["data"]["pip_name"] = p
                    req_data[-1]["data"]["version"] = v
                    req_data[-1]["data"]["python"] = py3_version
                    exfile = join(cmsdist, "pip", p + ".file")
                    if exists(exfile):
                        with open(exfile) as xref:
                            for xline in xref.readlines():
                                m = re.match("^%define\s+pip_name\s+([^\s]+)\s*$", xline.strip())
                                if m:
                                    req_data[-1]["data"]["pip_name"] = m.group(1)
                                    break
    return req_data


def check_updates(req_data):
    from datetime import datetime

    epoch = datetime.utcfromtimestamp(0)
    ignore_line = []
    ignored = []
    ignore_count = 0
    if not exists("cache"):
        os.system("mkdir -p cache")
    print("Checking for updates ...")
    for data in req_data:
        xline = data["line"].replace(" ", "")
        if xline == "":
            continue
        if xline.startswith("#"):
            m = re.match("#NO_AUTO_UPDATE:((\d+):|).*", xline)
            if m:
                try:
                    ignore_count = int(m.group(2))
                except:
                    ignore_count = 1
                ignore_line = [data["line"]]
            elif ignore_count:
                ignore_line.append("    " + data["line"])
            continue
        p = data["data"]["name"]
        op = data["data"]["pip_name"]
        ov = data["data"]["version"]
        if exists("cache/%s.json" % p):
            jdata = json.load(open("cache/%s.json" % p))
        else:
            o = subprocess.Popen(
                "curl -s -k -L https://pypi.python.org/pypi/%s/json" % (op),
                stdout=subprocess.PIPE,
                shell=True,
                universal_newlines=True,
            )
            jdata = json.loads(o.stdout.read())
            json.dump(jdata, open("cache/%s.json" % p, "w"), sort_keys=True, indent=2)
        if True:
            v = jdata["info"]["version"]
            if ignore_count:
                ignore_count -= 1
                if ov != v:
                    ignored.append(
                        "*** WARNING: %s: Newer version %s found (existing: %s) but not updating due to following comment in requitements.txt."
                        % (p, v, ov)
                    )
                    if ignore_line:
                        ignored.append("    %s" % ("\n".join(ignore_line)))
                ignore_line = []
                continue
            if "python" in data["data"]:
                py_ver = data["data"]["python"]
                # FIXME: Ignore python version check
                if False and not check_python_require(py_ver, jdata["info"]["requires_python"]):
                    releases = []
                    msg = []
                    for i in jdata["releases"]:
                        for d in jdata["releases"][i]:
                            if d["python_version"] != "source":
                                continue
                            if not check_python_require(py_ver, d["requires_python"]):
                                msg.append(
                                    "  INFO: %s: Ignoring version %s due to python requirement: %s%s"
                                    % (p, i, py_ver, d["requires_python"])
                                )
                                continue
                            uptime = (
                                datetime.strptime(d["upload_time"], "%Y-%m-%dT%H:%M:%S") - epoch
                            ).total_seconds()
                            releases.append(
                                {
                                    "version": i,
                                    "upload": uptime,
                                    "requires_python": d["requires_python"],
                                }
                            )
                            msg.append(
                                "  INFO: %s: Matched version %s due to python requirement: %s %s"
                                % (p, i, py_ver, d["requires_python"])
                            )
                    newlist = sorted(releases, key=lambda k: k["upload"])
                    if newlist:
                        v = newlist[-1]["version"]
                    if ov != v:
                        for m in msg:
                            print(m)
            if ov == v:
                continue
            m = re.match("^\s*%s\s*==\s*%s(\s*;.+|)$" % (p, ov), data["line"])
            try:
                data["line"] = "%s==%s%s" % (p, v, m.group(1))
                print("NEW:", p, ov, v)
            except:
                print("Wrong data:", p, ov, v)
    for i in ignored:
        print(i)


def rewrite_requiremets(red_data, cmsdist):
    req_file = requirements_file(cmsdist)
    with open(req_file, "w") as ref:
        for d in req_data:
            ref.write(d["line"] + "\n")


if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser(usage="%prog")
    parser.add_option(
        "-C",
        "--clean-cache",
        dest="clean_cache",
        action="store_true",
        help="Cleanup cache directory and re-check PyPI for updates.",
        default=False,
    )
    parser.add_option(
        "-u",
        "--update",
        dest="update",
        action="store_true",
        help="Update requirements.txt",
        default=False,
    )
    parser.add_option(
        "-c", "--cmsdist", dest="cmsdist", help="cmsdist directory", type=str, default="cmsdist"
    )
    opts, args = parser.parse_args()
    if opts.clean_cache:
        os.system("rm -rf cache")
    req_data = read_requirements(opts.cmsdist)
    check_updates(req_data)
    if opts.update:
        rewrite_requiremets(req_data, opts.cmsdist)
