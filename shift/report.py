import argparse
import os
import re
import sys
import urllib
import urllib.error

import libib

if sys.version_info.major < 3 or (
    sys.version_info.major == 3 and sys.version_info.minor < 6
):
    print("This script requires Python 3.6 or newer!", file=sys.stderr)
    exit(0)

date_rex = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}00")


def main():
    # print(f"Loaded {len(exitcodes)} exit code(s)")
    libib.setup_logging()
    libib.get_exitcodes()

    structure = libib.fetch("SDT/html/data/structure.json")

    if args.series == "default":
        default_release = structure["default_release"]
    else:
        default_release = args.series

    try:
        release_data = libib.fetch("SDT/html/data/" + default_release + ".json")
    except urllib.error.HTTPError:
        print(f"!ERROR: Invalid release {default_release}!")
        exit(1)

    ib_dates = [] if args.date else args.date

    if not ib_dates:
        latest_ib_date, previous_ib_date = None, None

        for i, c in enumerate(release_data["comparisons"]):
            if not c["isIB"]:
                continue

            latest_ib_date = release_data["comparisons"][i]["ib_date"]
            try:
                previous_ib_date = release_data["comparisons"][i + 1]["ib_date"]
            except IndexError:
                pass

            break

        print(f"Latest IB date: {latest_ib_date}")
        print(f"Previous IB date: {previous_ib_date}")

        if latest_ib_date is None:
            print(f"!ERROR: latest IB for {default_release} not found!")
            exit(1)

        if previous_ib_date is None:
            print(f"?WARNING: only one IB available for {default_release}")

        ib_dates = [latest_ib_date]
        if previous_ib_date is not None:
            ib_dates.append(previous_ib_date)

    os.makedirs("out", exist_ok=True)
    for ib_date in ib_dates:
        for flav, comp in libib.get_flavors(ib_date, default_release).items():
            release_name, errors = libib.check_ib(comp)
            with open(f"out/{release_name}_{ib_date}.md", "w") as f:
                print(f"## {release_name}\n", file=f)
                print("-- INSERT SCREENSHOT HERE --\n", file=f)
                for arch in errors:
                    print(f"### {arch}\n", file=f)
                    if any(errors[arch].items()):
                        print("| What failed | Description | Issue |", file=f)
                        print("| ----------- | ----------- | ----- |", file=f)
                        for error in errors[arch]["build"]:
                            # type error: libib.LogEntry
                            print(
                                f"| [{error.name}]({error.url}) | {error.data[1]}x "
                                f"{error.data[0]} | TDB |",
                                file=f,
                            )
                        for error in errors[arch]["utest"]:
                            print(
                                f"| [{error.name}]({error.url}) | TBD | TBD |", file=f
                            )

                        for error in errors[arch]["relval"]:
                            print(
                                f"| [{error.name}]({error.url}) | {error.data} | "
                                f"TBD |"
                            )
                    else:
                        print('<span style="color:green">No issues</span>', file=f)

            print("", file=f)


def validate_date(x):
    if not (x == "auto" or date_rex.match(x.rsplit("_")[1])):
        raise ValueError()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="CMSSDT Shift Assistant")
    parser.add_argument(
        "-s",
        "--series",
        default="default",
        help="Release series to process or 'default' to use 'default_release' from "
        "structure.json",
    )
    parser.add_argument(
        "-d",
        "--date",
        default="auto",
        type=validate_date,
        help="IB date to process (YYYY-MM-DD) or 'auto' to process two last IBs",
        nargs="*",
    )
    args = parser.parse_args()
    # main2()
    main()
