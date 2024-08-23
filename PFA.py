#!/usr/bin/python3
import os
import argparse
def find_file_path(file):
    if not os.path.isfile(file):
        return None
    return os.path.realpath(file)
def find_python_files(directory):
    py_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    return py_files
def CodeQualityChecks(python_files):
    if python_files:
        for file in python_files:
            file_path = find_file_path(file)
            if not file_path:
                print("File {} not found or invalid path.".format(file))
                continue

            format_command = "ruff format {}".format(file_path)
            print("Executing command: {}".format(format_command))  # Debug print
            os.system(format_command)
def main():
    parser = argparse.ArgumentParser(
        description="Linting and formatting Python files in directories or file paths."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="List of directories or file paths to process"
    )
    args = parser.parse_args()

    all_python_files = []
    for path in args.paths:
        if os.path.isdir(path):
            all_python_files.extend(find_python_files(path))
        elif os.path.isfile(path):
            all_python_files.append(path)
        else:
            print("Error: {} is not a valid file or directory.".format(path))
            return
    CodeQualityChecks(all_python_files)
if __name__ == "__main__":
    main()


