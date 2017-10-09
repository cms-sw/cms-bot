#!/usr/bin/env python

import argparse
import re
import os

# constants
html_start = '''
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
'''

html_end = '''
    </div>
<script>
$(document).ready(function() {
    $('#table-id').DataTable();
} );
</script>
</body>
</html>
'''

link_root = 'https://github.com/cms-sw/cmssw/blob/master/'
a_href = '<a href="{url}">{text}</a>'
table = '''<table class="table-bordered">\n\t{0}\n</table>\n'''
table_start = '''<table id="table-id" class="table-bordered display">\n'''
table_end = '''</tbody>\n</table>\n'''

tr = '<tr>\n{0}\n</tr>\n'  # row
th = '<th>{0}</th>'  # label column
td = '<td>{0}</td>'  # column
h1 = '<h1>t{0}\n</h1>\n'

# regex
regex_dashes = '^(-|=)*$'
regex_td = '^[ ]*[\d *]+.*\..+$'
# regex_th = '^[^\d\W]+$'
regex_th = '.*(NLOC|Total nloc)'
regex_H1_warnings = ' *^!+.*!+ *$'
regex_H1_no_warnings = 'No thresholds exceeded \('
regex_H1_files = '^\d+ file analyzed'
regex_split = "[ ]{2,}|[ ]*$]"
regex_split_td = "[ ]{1,}|[ ]*$]"
regex_line_to_url = "[a-zA-Z]"
regex_has_line_numbers = "@.+@"


def format_tag(tag, value):
    return tag.format(value)


def format_a_ref(url, text):
    return a_href.format(url=url, text=text)


#
#
# def format_html(title, content):
#     return html.format(title=title, content=content)


def get_args():
    '''This function parses and return arguments passed in'''
    # Assign description to the help doc
    parser = argparse.ArgumentParser(
        description='Script converts lizard .txt output to .html')

    # Add arguments
    parser.add_argument(
        '-s', '--source', type=str, help='Source file', required=True)
    parser.add_argument(
        '-d', '--dir', type=str, help='Output directory', required=True)

    # Array for all arguments passed to script
    args = parser.parse_args()

    # Assign args to variables
    source = args.source
    output_d = args.dir

    # Return all variable values
    return source, output_d


total_col_nr = 0  # global value


def text_with_href(url_base, line):
    # if convertable to line

    if bool(re.search(regex_line_to_url, line)):
        line_numbers_group = re.search(regex_has_line_numbers, line)
        if bool(line_numbers_group):
            lines_string = line_numbers_group.group(0)
            lines_string = lines_string.replace('@', '')
            lines = lines_string.split('-')

            line_split = re.split(regex_has_line_numbers, line)
            url = url_base + line_split[1] \
                  + "#" \
                  + "L{0}-L{1}".format(lines[0], lines[1])
            return a_href.format(url=url, text=line)
        else:
            return line  # TODO
    else:
        return line


def parse(file, line_previous, line):
    global total_col_nr

    if bool(re.search(regex_dashes, line)):
        return False

    elif bool(re.search(regex_th, line)):
        table_header_values = re.split(regex_split, line.strip())
        generated_row = ''
        for th_val in table_header_values:
            generated_row += th.format(th_val)
        file.write(
            '<thead>' + tr.format(generated_row) + '</thead>\n<tbody>'
        )
        total_col_nr = len(table_header_values) - 1
        return False

    elif bool(re.search(regex_td, line)):
        table_row_values = re.split(regex_split_td, line.strip(), maxsplit=total_col_nr)
        generated_row = ''
        for td_val in table_row_values[:-1]:
            generated_row += td.format(td_val)
        generated_row += td.format(
            text_with_href(link_root, table_row_values[-1])
        )

        file.write(
            tr.format(generated_row)
        )
        return False

    elif bool(re.search(regex_H1_files, line)):
        return True

    return False


def main(source_f_path, output_d):
    """Main function"""

    with open(source_f_path, 'r') as source_f:

        do_split = False
        previous_line = None

        html_0 = open(os.path.join(output_d, 'all_functions.html'), 'w')
        html_0.write(html_start.format(title='all_functions'))
        html_0.write(table_start)
        while do_split is False:
            line = source_f.readline()
            do_split = parse(html_0, previous_line, line)
            previous_line = line
            if not line:
                break
        html_0.write(table_end)
        html_0.write(html_end)
        html_0.close()
        # close open

        # open

        # open document to read

        # open document to write

        # open document


if __name__ == '__main__':
    main(get_args())
