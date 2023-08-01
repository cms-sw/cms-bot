import argparse
import libib
import re
import os

from dataclasses import dataclass, field

# noinspection PyUnresolvedReferences
from libib import PackageInfo, ErrorInfo


@dataclass(frozen=True)
class CompError:
    file: str
    line: int
    data: str = field(compare=False)
    url: str = field(compare=False)


error_rex = re.compile(
    r"<span class=compErr> <b> (?P<path>.*):(?P<line>\d+):(?P<col>\d+): error: (?P<text>.*)"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a", "--architecture", help="Release architecture (e.g. el9_amd64_gcc13)"
    )
    parser.add_argument("-d", "--date", help="IB date")
    parser.add_argument("-s", "--series", help="IB series (e.g. CMSSW_13_3_X)")
    parser.add_argument(
        "-f", "--filter", help="Only display errors containing given text"
    )

    args = parser.parse_args()

    print(f"Getting IB data for {args.series} on {args.date}")
    comp = libib.get_ib_comparision(args.date, args.series)[args.series]
    if comp is None:
        print(
            f"No errors found for IB {args.series} on {args.date} arch {args.architecture}"
        )
        return

    print(
        f"Extracting build errors for {args.series} on {args.date} arch {args.architecture}"
    )
    _, errors = libib.check_ib(comp, True)
    errors = errors[args.architecture]["build"]
    seen_errors = set()

    print("Collecting unique errors")
    for error in errors:
        if error.data[0] != "compError":
            continue
        pkg_name = "_".join(error.url.split("/")[-2:])
        print(f"> Checking {pkg_name}")
        if not os.path.exists(os.path.join("cache", pkg_name + ".html")):
            log_html = libib.fetch(error.url, libib.ContentType.TEXT)
            with open(os.path.join("cache", pkg_name + ".html"), "w") as f:
                f.write(log_html)
        else:
            log_html = open(os.path.join("cache", pkg_name + ".html")).read()

        for match in error_rex.finditer(log_html):
            error_x = CompError(
                file=os.path.basename(match.group("path")),
                line=match.group("line"),
                data=match.group("text"),
                url=error.url,
            )
            seen_errors.add(error_x)

    with open("errors.md", "w") as f:
        print("| Location | Error text |", file=f)
        print("| --- | --- |", file=f)
        for error in sorted(tuple(seen_errors), key=lambda x: (x.url, x.file, x.line)):
            # if 'error=array-bounds' in text:
            if (not args.filter) or args.filter in error.data:
                print(f"{error.url} -> {error.file}:{error.line} error {error.data}")
                print(
                    f"| [{error.file}:{error.line}]({error.url}) | {error.data} |",
                    file=f,
                )


if __name__ == "__main__":
    main()
