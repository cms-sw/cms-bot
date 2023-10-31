#!/usr/bin/env python

import argparse
import re
import os

# constants
html_start = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.10.16/css/jquery.dataTables.min.css">
    
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.2.0/jquery.min.js"></script>
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js"></script>
    <script src="https://code.jquery.com/jquery-1.12.4.js"></script>
    <script src="https://cdn.datatables.net/1.10.16/js/jquery.dataTables.min.js"></script>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
    <div class="container">
        <h1><b>{title}</b></h1>
        <hr>
"""

html_end = """
        <hr>
    </div>
<script>
$(document).ready(function() {{
    var data = {data};
    $('#table-id').DataTable({{
            order: [1, 'desc'], // order on CCN
            data: data,
            deferRender:    true,
            {comment_out_scrollX}scrollX: true,
            scrollCollapse: true,
            scroller:       true
        }}
    );
}} );
</script>
</body>
</html>
"""

g_total_col_nr = 0  # global value
g_link_root = "https://test/adress.com"
g_table_data = []

a_href = '<a href="{url}">{text}</a>'
table = """<table class="table-bordered">\n\t{0}\n</table>\n"""
table_start = """<table id="table-id" class="table-bordered display">\n"""
table_end = """</tbody>\n</table>\n"""

tr = "<tr>\n{0}\n</tr>\n"  # row
th = "<th>{0}</th>"  # label column
td = "<td>{0}</td>"  # column
h1_bold = "<h1><b>{0}\n</b></h1>\n"
h2 = "<h2 {klass}>{0}\n</h2>\n"

# regex
regex_dashes = "^(-|=)*$"
regex_td = "^[ ]*[\d *]+.*\..+$"
# regex_th = '^[^\d\W]+$'
regex_th = ".*(NLOC)"
regex_th_total = "^Total nloc"
regex_H1_warnings = " *^!+.*!+ *$"
regex_H1_no_warnings = "^No thresholds exceeded \("
regex_H1_files = "^\d+ file analyzed"
regex_split = "[ ]{2,}|[ ]*$]"
regex_split_td = "[ ]{1,}|[ ]*$]"
regex_line_to_url = "[a-zA-Z]"
regex_has_line_numbers = "@.+@"


def get_args():
    """
    This function parses and return arguments passed in
    """

    # Assign description to the help doc
    parser = argparse.ArgumentParser(description="Script converts lizard .txt output to .html")

    # Add arguments
    parser.add_argument("-s", "--source", type=str, help="Source file", required=True)
    parser.add_argument("-d", "--dir", type=str, help="Local output directory", required=True)
    parser.add_argument(
        "-l", "--link_root", type=str, help="Project's repository at Github", required=True
    )

    # Array for all arguments passed to script
    args = parser.parse_args()

    # Assign args to variables
    source = args.source
    output_d = args.dir
    link_root = args.link_root

    # Return all variable values
    return source, output_d, link_root


def text_with_href(url_base, line):
    # if convertible to line
    if bool(re.search(regex_line_to_url, line)):
        line_numbers_group = re.search(regex_has_line_numbers, line)
        if bool(line_numbers_group):
            lines_string = line_numbers_group.group(0)
            lines_string = lines_string.replace("@", "")
            lines = lines_string.split("-")

            line_split = re.split(regex_has_line_numbers, line)
            url = url_base + line_split[1] + "#" + "L{0}-L{1}".format(lines[0], lines[1])
            return a_href.format(url=url, text=line)
        else:
            url = url_base + line
            return a_href.format(url=url, text=line)
    else:
        return line


def parse(f_out, line):
    global g_total_col_nr, g_table_data

    if bool(re.search(regex_dashes, line)):
        return False

    elif bool(
        re.search(regex_H1_warnings, line)
        or (re.search(regex_H1_no_warnings, line))
        or (re.search(regex_th_total, line))
        or re.search(regex_H1_files, line)
    ):
        return True

    elif bool(re.search(regex_th, line)):
        write_table_th(f_out, line)
        return False

    elif bool(re.search(regex_td, line)):
        table_row_values = re.split(regex_split_td, line.strip(), maxsplit=g_total_col_nr)
        row_dataset = []
        for td_val in table_row_values[:-1]:
            row_dataset.append(td_val)
        row_dataset.append(text_with_href(g_link_root, table_row_values[-1]))
        g_table_data.append(row_dataset)
        return False

    return False


def write_table_th(f_out, line):
    global g_total_col_nr
    table_header_values = re.split(regex_split, line.strip())
    generated_row = ""
    for th_val in table_header_values:
        generated_row += th.format(th_val)
    f_out.write("<thead>" + tr.format(generated_row) + "</thead>\n<tbody>")
    g_total_col_nr = len(table_header_values) - 1


def main(source_f_path, output_d, link_root):
    """Main function"""
    global g_link_root, g_table_data
    g_link_root = link_root

    with open(source_f_path, "r") as source_f:

        do_split = False

        # --- { all_functions.html }
        html_0 = open(os.path.join(output_d, "all_functions.html"), "w")
        html_0.write(html_start.format(title="Statistics of all functions"))

        html_0.write(table_start)
        while do_split is False:
            line = source_f.readline()
            do_split = parse(html_0, line)
            if not line:
                break
        html_0.write(table_end)
        html_0.write(html_end.format(data=g_table_data, comment_out_scrollX=""))
        html_0.close()
        g_table_data = []
        # --- {END all_functions.html }

        # --- { file_statistics.html }
        html_0 = open(os.path.join(output_d, "file_statistics.html"), "w")
        html_0.write(html_start.format(title="Files statistics"))
        html_0.write(h2.format(line, klass=""))
        html_0.write(table_start)
        do_split = False
        while do_split is False:
            line = source_f.readline()
            do_split = parse(html_0, line)
            if not line:
                break
        html_0.write(table_end)
        html_0.write(html_end.format(data=g_table_data, comment_out_scrollX=""))
        html_0.close()
        g_table_data = []
        # --- {END file_statistics.html }

        # --- { warnings.html }
        html_0 = open(os.path.join(output_d, "warnings.html"), "w")
        html_0.write(html_start.format(title="Warnings"))

        h1_class = ""
        if bool(re.search(regex_H1_warnings, line)):
            h1_class = 'class="alert alert-danger"'

        html_0.write(h2.format(line, klass=h1_class))
        if bool(re.search(regex_H1_warnings, line)):
            html_0.write(table_start)
            do_split = False
            while do_split is False:
                line = source_f.readline()
                do_split = parse(html_0, line)
                if not line:
                    break
            html_0.write(table_end)

        html_0.write(html_end.format(data=g_table_data, comment_out_scrollX=""))
        html_0.close()
        g_table_data = []
        # --- {END warnings.html }

        # --- { total.html }
        html_0 = open(os.path.join(output_d, "total.html"), "w")
        html_0.write(html_start.format(title="Total scan statistics"))
        html_0.write(table_start)
        write_table_th(html_0, line)
        do_split = False
        while do_split is False:
            line = source_f.readline()
            do_split = parse(html_0, line)
            if not line:
                break
        html_0.write(table_end)
        html_0.write(html_end.format(data=g_table_data, comment_out_scrollX="//"))
        html_0.close()
        g_table_data = []
        # --- {END total.html }


if __name__ == "__main__":
    main(*get_args())
