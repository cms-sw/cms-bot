#!/usr/bin/env python
from __future__ import print_function
from es_utils import get_indexes, open_index, close_index, delete_index, send_request
import sys
import json
from time import sleep

if __name__ == "__main__":
    pattern = sys.argv[1]
    indexes = get_indexes("cmssdt-" + pattern + "*").splitlines()
    indexes_name_only = []
    opened_idxs_list = []
    closed_idxs_list = []

    for i in indexes:
        idx_list = opened_idxs_list
        if "open" not in i and "green" not in i:
            idx_list = closed_idxs_list
        list_of_recs = i.split()
        print(list_of_recs)
        for j in list_of_recs:
            if "cmssdt-" in j:
                indexes_name_only.append(j)
                idx_list.append(j)

    print("list with open idxs", opened_idxs_list)
    print("list with closed idx", closed_idxs_list)

    print("indexes names only")
    print(indexes_name_only)
    for i in indexes_name_only:
        print(i)
        current_idx = i
        tmp_idx = i + "_temppp"
        request_data = json.dumps({"source": {"index": current_idx}, "dest": {"index": tmp_idx}})
        print("request for reindex body: ", request_data)

        # open the index if its closed
        if current_idx in closed_idxs_list:
            open_index(current_idx)
        # wait 5 seconds
        sleep(5)

        request_finished_properly = send_request("_reindex/", request_data, method="POST")
        if request_finished_properly:
            print("forward reindexing complete, delete")
            delete_index(current_idx)
        else:
            print(
                "reindexing failed for ", current_idx, " to ", tmp_idx, ", crash the jenkins job"
            )
            exit(-1)
        # wait 5 seconds
        sleep(5)

        request_data = json.dumps({"source": {"index": tmp_idx}, "dest": {"index": current_idx}})
        request_finished_properly = send_request("_reindex/", request_data, method="POST")
        if request_finished_properly:
            print("reverse reindexing complete, delete the temp idx")
            delete_index(tmp_idx)
        else:
            print(
                "reindexing failed for ",
                tmp_idx,
                " to ",
                current_idx,
                ", crash the jenkins job, try manually",
            )
            exit(-1)
        # close the index if it was in the list of closed
        if current_idx in closed_idxs_list:
            close_index(current_idx)
