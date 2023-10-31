#!/usr/bin/env python3
"""
File       : jenkins-project-report-to-markdown.py
Author     : Zygimantas Matonis
Description: This script will generate markdown files from Jenkins project reports
"""
import json
import os
import re
import sys
from collections import defaultdict

parents = defaultdict(list)

# global parameters
jenkins_home = "https://cmssdt.cern.ch/jenkins/"
split_pat = "\*"  # to match bullet list in markdown

# markdown_output_dir = '/tmp/jenkins_reports/'
markdown_output_dir_name = "jenkins_reports"
project_report_section_name = "Jenkins Projects"


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


def write_markdown_file(view_data_dict, all_project_dict, markdown_output_dir):
    view_name = view_data_dict["name"]

    with open(markdown_output_dir + "/" + view_name.replace(" ", "-") + ".md", "w") as output_f:

        # write view description
        output_f.write("# [{0}]({1})\n\n".format(view_name, link_to_view(view_name)))
        output_f.write("**View description:** {0}\n\n".format(view_data_dict["description"]))
        output_f.write("**View type:** {0}\n\n".format(view_data_dict["view_type"]))

        output_f.write("---\n\n")
        output_f.write("# Projects:\n\n")

        # write project description
        for project in view_data_dict["project_names"]:
            project_data = all_project_dict[project]
            output_f.write("## [{0}]({1})\n\n".format(project, link_to_project(project)))

            output_f.write(
                "**Description:** {0}\n\n".format(
                    project_data["project_desc"] if project_data["project_desc"] else None
                )
            )

            # is project disabled
            status = "disabled" if project_data["is_disabled"] else "enabled"
            output_f.write("**Project is `{0}`.**\n\n".format(status))

            output_f.write("**Upstream projects:**\n")
            for pr in project_data["upstream"]:
                output_f.write("* [{0}](#{0}):\n".format(pr))
            output_f.write("\n")

            output_f.write("**Downstream projects:**\n")
            for pr in project_data["downstream"]:
                output_f.write("* [{0}](#{0}):\n".format(pr))
            output_f.write("\n")

            output_f.write("**Sub-projects:**\n")
            for pr in project_data["subprojects"]:
                output_f.write("* [{0}](#{0}):\n".format(pr))
            output_f.write("\n")

            # TODO look what for trigger is
            output_f.write("**Triggers from:** {0}\n\n".format(project_data["triggers_from"]))

            cron_tabs_list = project_data["scheduled_triggers"]
            cron_message = (
                cron_tabs_list[0][1] if len(cron_tabs_list) > 0 else "Not periodically build"
            )
            periodic_builds_message = """
**Periodic builds:**
```bash
{0}
```

---

""".format(
                cron_message
            )
            output_f.write(periodic_builds_message)


def write_readme(markdown_output_dir):
    readme_message = """
# {0}

This is automatically generated documentation of Jenkins jobs. **All changes in this directory will be overwritten 
by scheduled job.** In oder to update the documentation, edit project description in Jenkins instead.

""".format(
        project_report_section_name
    )
    with open(markdown_output_dir + "/README.md", "w") as output_f:
        output_f.write(readme_message)


def create_uncategorized_view(view_dict, all_project_dict):
    uncategorized_p_list = []

    for _, project in all_project_dict.items():
        is_uncategorized = True
        for _, view_data_dict in view_dict.items():
            if view_data_dict["name"] == "All":
                continue
            if project["project_name"] in view_data_dict["project_names"]:
                is_uncategorized = False
                break
        if is_uncategorized:
            uncategorized_p_list.append(project["project_name"])

    return {
        "name": "Uncategorized",
        "view_type": "Custom",
        "description": "This view contains all projects that were not categorized.",
        "project_names": uncategorized_p_list,
    }


def main(args):
    """
    :param args:
        1: path to input JSON
        2: path to output dir
        3: path to wiki dir
    """
    global sum_f
    data_json_f_path = args[0]
    markdown_output_dir = args[1]
    wiki_dir = args[2]

    views_names_list = []

    try:
        fd = open(data_json_f_path)
        txt = fd.read()
    except Exception as e:
        print("Error reading the file" + e)

    # creates ouput directory if it doesn't exist already
    if not os.path.exists(markdown_output_dir):
        os.makedirs(markdown_output_dir)

    # loads data to dictionary
    data_dict = json.loads(txt)

    data_dict["views"]["uncategorized"] = create_uncategorized_view(
        data_dict["views"], data_dict["projects"]
    )
    # create README.md for folder
    write_readme(markdown_output_dir)

    # create markdown files
    for view_key, view_data_dict in data_dict["views"].items():
        write_markdown_file(view_data_dict, data_dict["projects"], markdown_output_dir)
        views_names_list.append(view_data_dict["name"])

    # edit summary.md in wiki dir to include generated report
    try:
        sum_f = open(wiki_dir + "/SUMMARY.md", "r+")
        summary_lines = sum_f.readlines()
    except Exception as e:
        print("Error reading the SUMMARY.md file" + e)

    sum_f.seek(0)
    summary_iterator = iter(summary_lines)
    for line in summary_iterator:
        if project_report_section_name not in line:
            sum_f.write(line)
        else:
            # write new summary
            indent_size = len(re.split(split_pat, line, 1)[0])
            config_dict = {
                "indentation": " " * indent_size,
                "view_name": project_report_section_name,
                "file_name": "README.md",
                "report_dir": markdown_output_dir_name,
            }
            sum_f.write(
                "{indentation}* [{view_name}]({report_dir}/{file_name})\n".format(**config_dict)
            )

            for name in views_names_list:
                config_dict = {
                    "indentation": " " * (indent_size + 2),
                    "view_name": name,
                    "file_name": name.replace(" ", "-") + ".md",
                    "report_dir": markdown_output_dir_name,
                }
                sum_f.write(
                    "{indentation}* [{view_name}]({report_dir}/{file_name})\n".format(
                        **config_dict
                    )
                )

            # discard old entries of Jenkins projects
            is_old_line = True
            end_of_file = False
            while is_old_line:
                try:
                    line = next(summary_iterator)
                except Exception as e:
                    # no more lines to read
                    end_of_file = True
                    break
                child_indent_size = len(re.split(split_pat, line, 1)[0])
                is_old_line = True if child_indent_size > indent_size else False
            if not end_of_file:
                sum_f.write(line)

    sum_f.truncate()
    sum_f.close()


if __name__ == "__main__":
    main(sys.argv[1:])
