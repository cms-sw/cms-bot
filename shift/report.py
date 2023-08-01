import argparse
import os
import sys
import urllib
import urllib.error

import libib

# noinspection PyUnresolvedReferences
from libib import PackageInfo, ErrorInfo

if sys.version_info.major < 3 or (
    sys.version_info.major == 3 and sys.version_info.minor < 6
):
    print("This script requires Python 3.6 or newer!", file=sys.stderr)
    exit(0)


def main():
    # print(f"Loaded {len(exitcodes)} exit code(s)")
    libib.setup_logging()
    libib.get_exitcodes()

    structure = libib.fetch("SDT/html/data/structure.json")

    if args.series == "default":
        series = structure["default_release"]
    else:
        series = args.series

    try:
        libib.fetch("SDT/html/data/" + series + ".json")
    except urllib.error.HTTPError:
        print(f"!ERROR: Invalid release {series}!")
        exit(1)

    if (not args.date) or args.date == "auto":
        ib_dates = libib.get_ib_dates(series)
    else:
        ib_dates = [args.date]

    os.makedirs("out", exist_ok=True)
    for ib_date in ib_dates:
        for flav, comp in libib.get_ib_comparision(ib_date, series).items():
            if comp is None:
                # print(f"No IB found for flavor {flav} and date {ib_date}")
                continue
            release_name, errors = libib.check_ib(comp)
            with open(f"out/{release_name}.md", "w") as f:
                print(f"## {release_name}\n", file=f)
                print("-- INSERT SCREENSHOT HERE --\n", file=f)
                for arch in errors:
                    print(f"### {arch}\n", file=f)
                    if any(
                        (
                            errors[arch]["build"],
                            errors[arch]["utest"],
                            errors[arch]["relval"],
                        )
                    ):
                        print("| What failed | Description | Issue |", file=f)
                        print("| ----------- | ----------- | ----- |", file=f)
                        for error in errors[arch]["build"]:
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
                                f"TBD |",
                                file=f,
                            )
                    else:
                        print('<span style="color:green">No issues</span>', file=f)

                    print("", file=f)


def validate_date(x):
    if not (x == "auto" or libib.date_rex.match(x.rsplit("_", 1)[1])):
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
    main()
