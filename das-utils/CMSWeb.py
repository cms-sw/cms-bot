#!/usr/bin/env python
from __future__ import print_function
from os import getuid
import json
import sys
from os.path import dirname, abspath

sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import urlencode, HTTPSConnection

# FIXME - is this script is used ?
def format(s, **kwds):
    return s % kwds


class CMSWeb(object):
    def __init__(self):
        self.URL_CMSWEB_BASE = "cmsweb.cern.ch"
        self.URL_PHEDEX_BLOCKREPLICAS = "/phedex/datasvc/json/prod/blockreplicas"
        self.URL_DBS_DATASETS = "/dbs/prod/global/DBSReader/datasets"
        self.URL_DBS_FILES = "/dbs/prod/global/DBSReader/files"
        self.URL_DBS_RUNS = "/dbs/prod/global/DBSReader/runs"
        self.URL_DBS_BLOCKS = "/dbs/prod/global/DBSReader/blocks"
        self.conn = HTTPSConnection(
            self.URL_CMSWEB_BASE, cert_file="/tmp/x509up_u{0}".format(getuid()), timeout=30
        )
        self.reply_cache = {}
        self.last_result = ""
        self.errors = 0

    def __del__(self):
        self.conn.close()

    def get_cmsweb_data(self, url):
        self.last_result = url
        if url in self.reply_cache:
            return True, self.reply_cache[url]
        msg = ""
        try:
            self.conn.request("GET", url)
            msg = self.conn.getresponse()
            if msg.status != 200:
                self.errors = self.errors + 1
                print("Result: {0} {1}: {2}".format(msg.status, msg.reason, url))
                return False, {}
            self.reply_cache[url] = json.loads(msg.read())
            return True, self.reply_cache[url]
        except Exception as e:
            print("Error:", e, url)
            self.errors = self.errors + 1
            return False, {}

    def search(self, lfn):
        lfn_data = {
            "ds_status": "UNKNOWN",
            "ds_block": "UNKNOWN",
            "ds_owner": "UNKNOWN",
            "at_cern": "UNKNOWN",
            "dataset": "UNKNOWN",
            "ds_files": "0",
        }

        # Find the block
        jmsg = self.search_lfn(lfn)
        if not jmsg:
            return lfn_data
        block = jmsg[0]["block_name"]
        dataset = jmsg[0]["dataset"]
        lfn_data["ds_block"] = block
        lfn_data["dataset"] = dataset

        # Check if dataset is still VALID
        status, res = self.search_dataset_status(dataset)
        if status:
            lfn_data["ds_status"] = res

        # Check if dataset/block exists at T2_CH_CERN and belongs to IB RelVals group
        status, res = self.search_block(block)
        if status:
            for x in res:
                lfn_data[x] = res[x]
        return lfn_data

    def search_block(self, block):
        status, jmsg = self.get_cmsweb_data(
            "{0}?{1}".format(self.URL_PHEDEX_BLOCKREPLICAS, urlencode({"block": block}))
        )
        if not status:
            return False, {}
        if len(jmsg["phedex"]["block"]) == 0:
            return False, {}
        block_data = {"at_cern": "no", "replicas": [], "ds_files": "0", "ds_owner": "UNKNOWN"}
        for replica in jmsg["phedex"]["block"][0]["replica"]:
            if (not "group" in replica) or (not replica["group"]):
                continue
            block_data["replica"].append(replica["node"])
            block_data["ds_files"] = str(replica["files"])
            block_data["ds_owner"] = replica["group"].strip().replace(" ", "_")
            if replica["node"] == "T2_CH_CERN":
                block_data["at_cern"] = "yes"
        return True, block_data

    def search_dataset_status(self, dataset):
        status, jmsg = self.get_cmsweb_data(
            "{0}?{1}".format(
                self.URL_DBS_DATASETS,
                urlencode({"detail": 1, "dataset_access_type": "*", "dataset": dataset}),
            )
        )
        if not status:
            return False, ""
        return True, jmsg[0]["dataset_access_type"].strip().replace(" ", "_")

    def search_lfn(self, lfn):
        status, jmsg = self.get_cmsweb_data(
            "{0}?{1}".format(
                self.URL_DBS_BLOCKS, urlencode({"detail": 1, "logical_file_name": lfn})
            )
        )
        if not status:
            return {}
        return jmsg

    def search_files(self, dataset):
        status, jmsg = self.get_cmsweb_data(
            "{0}?{1}".format(self.URL_DBS_FILES, urlencode({"detail": 1, "dataset": dataset}))
        )
        if not status:
            return {}
        return jmsg

    def search_runs(self, dataset):
        status, jmsg = self.get_cmsweb_data(
            "{0}?{1}".format(self.URL_DBS_RUNS, urlencode({"dataset": dataset}))
        )
        if not status:
            return {}
        return jmsg

    def search_blocks(self, dataset):
        status, jmsg = self.get_cmsweb_data(
            "{0}?{1}".format(self.URL_DBS_BLOCKS, urlencode({"dataset": dataset, "detail": 1}))
        )
        if not status:
            return {}
        return jmsg


if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser(usage="%prog <input>")
    opts, args = parser.parse_args()

    cmsweb = None
    for data in args:
        if not cmsweb:
            cmsweb = CMSWeb()
        if data.endswith(".root"):
            cmsweb.search(data, {})
        else:
            cmsweb.search_dataset(data.split("#")[0])
            if "#" in data:
                cmsweb.search_block(data)
        info = {data: cmsweb.reply_cache}
        print(json.dumps(info, indent=2, sort_keys=True, separators=(",", ": ")))
        cmsweb.reply_cache = {}
