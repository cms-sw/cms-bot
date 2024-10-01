from process_pr import get_package_categories, cmssw_file2Package
from argparse import ArgumentParser
from collections import defaultdict

import sys

from os.path import expanduser, dirname, abspath, join, exists

SCRIPT_DIR = dirname(abspath(sys.argv[0]))


def main():
    parser = ArgumentParser(description="Get category name(s) for given files")
    parser.add_argument(
        "-r",
        "--repo",
        dest="repository",
        default="cms-sw/cmssw",
        help="Github Repositoy name e.g. cms-sw/cmssw",
    )
    parser.add_argument("filename", nargs="+", metavar="FILE", help="File name(s)")
    args = parser.parse_args()

    repo_dir = join(SCRIPT_DIR, "repos", args.repository.replace("-", "_"))
    if exists(repo_dir):
        sys.path.insert(0, repo_dir)
    import repo_config

    all_cats = set()

    for filename in args.filename:
        cats = get_package_categories(cmssw_file2Package(repo_config, filename))
        all_cats.update(cats)
        print(filename, "->", ", ".join(cats))

    print("=" * 80)
    print(", ".join(all_cats))


if __name__ == "__main__":
    main()
