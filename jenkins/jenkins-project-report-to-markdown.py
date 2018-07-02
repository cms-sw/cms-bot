#!/usr/bin/env python2
"""
File       : jenkins-project-report-to-markdown.py
Author     : Zygimantas Matonis
Description: This script will generate markdown files from Jenkins project reports
"""

import json
import os
import sys
from collections import defaultdict

parents = defaultdict(list)

jenkins_home = 'https://cmssdt.cern.ch/jenkins/'
markdown_output_dir = '/tmp/jenkins_reports/'


def h1_str(value):
    return "# " + value + "\n\n"


def h2_str(value):
    return "## " + value + "\n\n"


def h3_str(value):
    return "### " + value + "\n\n"


def pr_str(value):
    return value + "\n\n"


def bold_str(value):
    return "*" + value + "*"


def link_to_view(value):
    return jenkins_home + "view/" + value


def link_to_project(value):
    return jenkins_home + "job/" + value


def write_markdown_file(view_data_dict, all_project_dict):
    view_name = view_data_dict['name']

    with open(markdown_output_dir + view_name + ".md", 'w') as output_f:

        # write view description
        output_f.write("# [{0}]({1})\n\n".format(view_name, link_to_view(view_name)))
        output_f.write("**View description:** {0}\n\n".format(view_data_dict['description']))
        output_f.write("**View type:** {0}\n\n".format(view_data_dict['view_type']))

        output_f.write("---\n\n")
        output_f.write("# Projects:\n\n")

        # write project description
        for project in view_data_dict['project_names']:
            project_data = all_project_dict[project]
            output_f.write("## [{0}]({1})\n\n".format(project, link_to_project(project)))

            output_f.write("**Description:** {0}\n\n".format(
                project_data['project_desc'] if project_data['project_desc'] else None
            ))

            output_f.write("**Upstream projects:**\n\n")
            for pr in project_data['upstream']:
                output_f.write("* [{0}](#{0}):\n".format(pr))
            output_f.write("\n")

            output_f.write("**Downstream projects:**\n\n")
            for pr in project_data['downstream']:
                output_f.write("* [{0}](#{0}):\n".format(pr))
            output_f.write("\n")

            output_f.write("**Sub-projects:**\n\n")
            for pr in project_data['subprojects']:
                output_f.write("* [{0}](#{0}):\n".format(pr))
            output_f.write("\n")

            # TODO look what for trigger is
            output_f.write("**Triggers from:** {0}\n\n".format(project_data['triggers_from']))


def main(args):
    """
    :param args:
        1: path to input JSON
    """
    data_json_f_path = args[0]
    try:
        fd = open(data_json_f_path)
        txt = fd.read()
    except Exception as e:
        print "Error reading the file" + e

    # creates ouput directory if it doesn't exist already
    if not os.path.exists(markdown_output_dir):
        os.makedirs(markdown_output_dir)

    # loads date to dictionary
    data_dict = json.loads(txt)

    for viewKey, viewData in data_dict['views'].items():
        write_markdown_file(viewData, data_dict['projects'])


if __name__ == '__main__':
    main(sys.argv[1:])
