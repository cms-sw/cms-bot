import github_utils
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", "-r")
    parser.add_argument("--commit", "-c")
    parser.add_argument("--architecture", "-a")
    parser.add_argument("--queue", "-u", required=False)
    parser.add_argument("--prefix", "-p")
    args = parser.parse_args()

    status_suffix = args.architecture
    if args.queue:
        flavor = args.queue.split("_")[3]
        if flavor == "X":
            flavor = "default"

        status_suffix = flavor + "/" + status_suffix

    all_statuses = github_utils.get_combined_statuses(args.commit, args.repository).get(
        "statuses", []
    )
    index = 0

    for status in all_statuses:
        if (
            status["context"].startswith(args.prefix + "/" + status_suffix)
            and status["state"] == "pending"
        ):
            with open("update-pr-status-{0}.prop".format(index), "w") as f:
                f.write("REPOSITORY={0}\n".format(args.repository))
                f.write("PULL_REQUEST={0}\n".format(args.commit))
                f.write("CONTEXT={0}\n".format(status["context"]))
                f.write("STATUS=error\n")
                f.write("STATUS_MESSAGE=Stuck due to all nodes being offline\n")

            index = index + 1


if __name__ == "__main__":
    main()
