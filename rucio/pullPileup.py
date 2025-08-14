#!/usr/bin/env python3
import glob, os, pwd, shlex, subprocess, sys
from argparse import ArgumentParser
from hashlib import md5
from io import BytesIO
from json import loads, dump
from pycurl import Curl


def getOS():
    """Gets OS version from shell (other methods return host OS when in container)"""
    cmd = r"sed -nr 's/[^0-9]*([0-9]+).*/\1/p' /etc/redhat-release"
    osv = subprocess.check_output(shlex.split(cmd), encoding="utf-8").rstrip()
    return osv


def getRucio(user):
    """Adds Rucio libraries to python path with requisite environment variables"""
    osv = getOS()
    rucio_path = f"/cvmfs/cms.cern.ch/rucio/x86_64/rhel{osv}/py3/current"
    os.environ["RUCIO_HOME"] = rucio_path
    os.environ["RUCIO_ACCOUNT"] = user
    full_rucio_path = glob.glob(rucio_path + "/lib/python*.*")[0]
    sys.path.insert(0, full_rucio_path + "/site-packages/")


def pull():
    """Pulls all data from ms-pileup"""
    cert, key = getX509()
    link = f"https://cmsweb-prod.cern.ch/ms-pileup/data/pileup?"
    buffer = BytesIO()
    c = Curl()
    c.setopt(c.URL, link)
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.CAINFO, None)
    c.setopt(c.SSLCERT, cert)
    c.setopt(c.SSLKEY, key)
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.SSL_VERIFYPEER, False)
    c.perform()
    c.close()
    body = buffer.getvalue()
    body = body.decode("iso-8859-1")
    return loads(body)["result"]


def getX509():
    """Helper function to get x509s from env or tmp file"""
    proxy = os.environ.get("X509_USER_PROXY", "")
    if proxy:
        return proxy, proxy
    else:
        proxy = "/tmp/x509up_u%s" % pwd.getpwuid(os.getuid()).pw_uid
        if os.path.isfile(proxy):
            return proxy, proxy
        else:
            certFile = os.environ.get("X509_USER_CERT", "")
            keyFile = os.environ.get("X509_USER_KEY", "")
            if certFile and keyFile:
                return certFile, keyFile
            else:
                return "", ""


def main(user):
    """Enumerates pileup containers and their respective lfns"""
    getRucio(user)
    from rucio.client.client import Client

    client = Client()
    pileup = ""
    for params in pull():
        files = []
        if params["active"]:
            if params["customName"]:
                fileList = list(client.list_files("group.wmcore", params["customName"]))
            else:
                fileList = list(client.list_files("cms", params["pileupName"]))
        else:
            fileList = None
        if fileList:
            for file in fileList:
                files += [file["name"]]
        else:
            files = []
        with open(f'{md5(params["pileupName"].encode()).hexdigest()}.txt', "w") as f:
            f.write("\n".join(str(i) for i in files))
        pileup += f'{params["pileupName"]} {md5(params["pileupName"].encode()).hexdigest()}.txt \n'
    with open("pileup_mapping.txt", "w") as f:
        f.write(pileup)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--user", default=os.getlogin(), help="user used to query Rucio")
    args = parser.parse_args()
    main(args.user)
