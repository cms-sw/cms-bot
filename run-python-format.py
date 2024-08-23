#!/usr/bin/python3
import os
import argparse
def main():
    parser = argparse.ArgumentParser(description="Run Python formatting and linting.")
    parser.add_argument(
        "--inputfile",
        required=True,
        help="Path to the file containing the list of files to process.",
    )
    parser.add_argument(
        "--cmsswbase",
        required=True,
        help="Path to the CMSSW base directory.",
    )
    args = parser.parse_args()

    input_file = args.inputfile
    cmssw_base = args.cmsswbase

    if not os.path.isfile(input_file):
        print("Error: {} does not exist.".format(input_file))
        return
    try:
        with open(input_file, "r") as file:
            files_list = [
                os.path.join(cmssw_base, line.strip()) for line in file if line.strip()
            ]
    except IOError as e:
        print("Error reading {}: {}".format(input_file, e))
        return
    with open("python-linting.txt", "w") as linting_output:
        if not files_list:
            linting_output.write("No files to check.\n")
            print("No files to check. Exiting.")
            return

        all_checks_passed = True
        for file in files_list:
            if os.path.isfile(file):
                check_command = "ruff check {} >> python-linting.txt".format(file)
                result = os.system(check_command)
                if result != 0:
                    all_checks_passed = False

        if all_checks_passed:
            linting_output.write("All checks passed!\n")

    print("Python linting completed. Check 'python-linting.txt' for details.")
    pfa_command = (
        "python3 ../cms-bot/PFA.py "
        + " ".join(files_list)
    )

    format_result = os.system(pfa_command)

    if format_result == 0:
        print("Successfully formatted files.")
    else:
        print("An error occurred while running PFA.py. Exit code: {}".format(format_result))

if __name__ == "__main__":
    main()

