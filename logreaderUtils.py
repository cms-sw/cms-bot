#! /usr/bin/env python
import json
import re


def add_exception_to_config(line, index, config_list, custom_rule_list=[]):
    default_rules_list = [
        # will ignore " IgnoreCompletely" messages
        {"str_to_match": "Begin(?! IgnoreCompletely)(.*Exception)", "name": "{0}"},
        # {"str_to_match": "\sException", "name": "Exception"},
        {"str_to_match": "edm::service::InitRootHandlers", "name": "Segmentation fault"}
    ]
    line_nr = index+1
    for rule in default_rules_list + custom_rule_list:
        match = re.search(rule["str_to_match"], line, re.IGNORECASE);
        if match:
            try:
                name = rule["name"].format(*match.groups())
            except:
                name = rule["name"]
            new_exception_config = {
                "lineStart": line_nr,
                "lineEnd": line_nr,
                "name": name + " at line #" + str(line_nr)
            }
            config_list.append(new_exception_config)
            return config_list
    return config_list


def write_config_file(log_reader_config_path, config_list):
    try:
        log_reader_config_f = open(log_reader_config_path, "w")
        json.dump({"list_to_show": config_list}, log_reader_config_f)
        log_reader_config_f.close()
    except:
        print("Error writing exception file")

