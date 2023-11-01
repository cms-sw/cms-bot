#! /usr/bin/env python
from __future__ import print_function
import json
import re


# Improvised enum
class ResultTypeEnum(object):
    TEST = "Tests"
    ISSUE = "Issues"


# Do not forget to include to list if ResultTypeEnum is updated
# Will be same ordering as in Log reader interface
all_controls = [ResultTypeEnum.ISSUE, ResultTypeEnum.TEST]


def add_exception_to_config(line, index, config_list, custom_rule_list=[]):
    default_rules_list = [
        {
            # will ignore " IgnoreCompletely" messages
            "str_to_match": "Begin(?! IgnoreCompletely)(.*Exception)",
            "name": "{0}",
            "control_type": ResultTypeEnum.ISSUE,
        },
        {
            "str_to_match": "edm::service::InitRootHandlers",
            "name": "Segmentation fault",
            "control_type": ResultTypeEnum.ISSUE,
        },
        {
            "str_to_match": "sig_dostack_then_abort",
            "name": "sig_dostack_then_abort",
            "control_type": ResultTypeEnum.ISSUE,
        },
        {
            "str_to_match": ": runtime error:",
            "name": "Runtime error",
            "control_type": ResultTypeEnum.ISSUE,
        },
        {
            "str_to_match": ": Assertion .* failed",
            "name": "Assertion failure",
            "control_type": ResultTypeEnum.ISSUE,
        },
        {
            "str_to_match": "==ERROR: AddressSanitizer:",
            "name": "Address Sanitizer error",
            "control_type": ResultTypeEnum.ISSUE,
        },
    ]
    line_nr = index + 1

    for rule in default_rules_list + custom_rule_list:
        match = re.search(rule["str_to_match"], line, re.IGNORECASE)
        if match:
            try:
                name = rule["name"].format(*match.groups())
            except:
                name = rule["name"]
            new_exception_config = {
                "lineStart": line_nr,
                "lineEnd": line_nr,
                "name": name + " at line #" + str(line_nr),
                "control_type": rule["control_type"],
            }
            config_list.append(new_exception_config)
            return config_list
    return config_list


def transform_and_write_config_file(log_reader_config_path, config_list):
    """
    Dumps config object as JSON file. It is used with for logreader web interface to mark particular issues in log file.
    Before dumping, tansform to suitable format.
    :param log_reader_config_path:
    :param config_list:
    :return:
    """

    def transform_config(config_list):
        show_controls = []
        for control_type in all_controls:
            issue_list = []
            for issue in config_list:
                if issue["control_type"] == control_type:
                    issue_list.append(issue)
            if len(issue_list) > 0:
                show_controls.append({"name": control_type, "list": issue_list})

        return show_controls

    try:
        log_reader_config_f = open(log_reader_config_path, "w")

        json.dump({"show_controls": transform_config(config_list)}, log_reader_config_f)
        log_reader_config_f.close()
    except:
        print("Error writing exception file.")
