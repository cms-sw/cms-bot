import github_utils
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", "-r")
    parser.add_argument("--commit", "-c")
    parser.add_argument("--prefix", "-p")
    parser.add_argument("suffix")
    args = parser.parse_args()

    status_prefix = f"{args.prefix}/"

    all_statuses = github_utils.get_combined_statuses(args.commit, args.repository).get(
        "statuses", []
    )

    for status in all_statuses:
        if (
            status["context"].startswith(status_prefix)
            and status["context"].endswith(f"/{args.suffix}")
            and status["state"] == "pending"
        ):
            github_utils.mark_commit_status(
                args.commit,
                args.repository,
                status["context"],
                "success",
                "",
                "Timed out waiting for node",
            )


if __name__ == "__main__":
    main()
