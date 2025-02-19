import github_utils
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", "-r")
    parser.add_argument("--commit", "-c")
    parser.add_argument("--prefix", "-p")
    args = parser.parse_args()

    status_prefix = f"{args.prefix}/"

    all_statuses = github_utils.get_combined_statuses(args.commit, args.repository).get(
        "statuses", []
    )
    index = 0

    for status in all_statuses:
        if (
            status["context"].startswith(status_prefix)
            and status["context"].endswith("/rocm")
            and status["state"] == "pending"
        ):
            with open("update-pr-status-{0}.prop".format(index), "w") as f:
                f.write("REPOSITORY={0}\n".format(args.repository))
                f.write("PULL_REQUEST={0}\n".format(args.commit))
                f.write("CONTEXT={0}\n".format(status["context"]))
                f.write("STATUS=success\n")
                f.write("STATUS_MESSAGE=Timed out waiting for node\n")

            index = index + 1


if __name__ == "__main__":
    main()
