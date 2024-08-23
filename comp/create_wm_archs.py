#!/usr/bin/env python3
from subprocess import getstatusoutput
from os.path import join, dirname, exists
from sys import exit

CMS_CVMFS = "/cvmfs/cms.cern.ch"
COMP_DIR = "%s/COMP" % CMS_CVMFS
ENV_FILE = join("etc", "profile.d", "init.sh")
FUTURE_PKGS = ["py2-future", "py3-future"]
FUTURE_PKG = "py3-future"
FUTURE_VERSION = "0.18.2"
WM_ARCHS = {
    "rhel5_x86_64": ["slc5_amd64_gcc434"],
    "rhel7_x86_64": ["slc7_amd64_gcc630"],
    "rhel6_x86_64": ["slc6_amd64_gcc700", {"python3": "3.6.4", "py2-future": "0.16.0"}],
    "rhel7_ppc64le": ["slc7_ppc64le_gcc820", {"python3": "3.8.2", "py2-future": "0.18.2"}],
    "rhel7_aarch64": ["slc7_aarch64_gcc820", {"python3": "3.8.2", "py2-future": "0.18.2"}],
    "rhel8_x86_64": ["cc8_amd64_gcc9", {"python3": "3.8.2", "py3-future": "0.18.2"}],
    "rhel8_aarch64": ["cc8_aarch64_gcc9", {"python3": "3.8.2", "py3-future": "0.18.2"}],
    "rhel8_ppc64le": ["cc8_ppc64le_gcc9", {"python3": "3.8.2", "py3-future": "0.18.2"}],
    "rhel9_x86_64": ["cs9_amd64_gcc11", {"python3": "3.9.6", "py3-future": "0.18.2"}],
}


def runcmd(cmd, debug=True):
    if debug:
        print("Running: ", cmd)
    e, out = getstatusoutput(cmd)
    if e:
        print(out)
        exit(1)
    return out


def create_default_links(comp_ver, def_ver):
    if not exists(def_ver):
        cmd = "mkdir -p {0} && ln -s {1} {2}".format(dirname(def_ver), comp_ver, def_ver)


def find_cms_version(arch, pkg, ver):
    out = runcmd("ls -d %s/%s/external/%s/%s*" % (CMS_CVMFS, arch, pkg, ver), debug=False)
    mver = ""
    for v in out.split("\n"):
        mver = v
        if v.endswith(ver):
            break
    return mver


def create_comp_package(arch, pkg, ver, cmspkg):
    comp_pkg = join(arch, "external", pkg)
    comp_ver = join(comp_pkg, ver)
    if pkg == "python3":
        if not exists(comp_ver):
            cmd = "ln -s {0} {1}".format(cmspkg, comp_ver)
            if not exists(comp_pkg):
                cmd = "mkdir -p {0} && {1}".format(comp_pkg, cmd)
            runcmd(cmd)
    elif pkg in FUTURE_PKGS:
        comp_init = join(comp_ver, ENV_FILE)
        if not exists(comp_init):
            comp_dir = dirname(comp_init)
            cms_init = join(cmspkg, ENV_FILE)
            cmd = "cp -fp {0} {1} && sed -i -e '/dependencies-setup/d;/PYTHON27PATH=/d;/LD_LIBRARY_PATH=/d' {1}".format(
                cms_init, comp_init
            )
            cmd += " && sed -i -e 's/PYTHON3PATH/PYTHONPATH/g' {0}".format(comp_init)
            if not exists(comp_dir):
                cmd = "mkdir -p {0} && {1}".format(comp_dir, cmd)
            runcmd(cmd)
        def_future = join(arch, "external", FUTURE_PKG, FUTURE_VERSION)
        if not exists(def_future):
            comp_ver = ver if FUTURE_PKG == pkg else "../%s/%s" % (pkg, ver)
            runcmd(
                "mkdir -p {0} && ln -s {1} {2}".format(dirname(def_future), comp_ver, def_future)
            )
    else:
        print("ERROR: Unknown package %s" % pkg)
        return False
    return True


for arch in WM_ARCHS:
    arch_data = WM_ARCHS[arch]
    sarch = arch_data[0]
    if len(arch_data) > 1:
        for pkg in arch_data[1]:
            ver = arch_data[1][pkg]
            cmspkg = find_cms_version(sarch, pkg, ver)
            if not (cmspkg and create_comp_package(sarch, pkg, ver, cmspkg)):
                exit(1)
    elif not exists(sarch):
        print("ERROR: Missing %s installation area" % sarch)
        exit(1)
    if not exists(arch):
        runcmd("ln -s {0} {1}".format(sarch, arch))
