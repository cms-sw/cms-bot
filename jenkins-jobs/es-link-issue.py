import base64
import json
import os
import time

import es_utils


def index_document(index, payload):
    payload["@timestamp"] = int(time.time() * 1000)
    payload = json.dumps(payload)

    response = es_utils.send_payload(f"cmssdt-{index}-failures", index, None, payload)


def main():
    data = os.getenv("DATA", None)
    issue_no = os.getenv("ISSUE", None)
    if not data:
        print("ERROR: No data")
        exit(1)
    if not issue_no:
        print("ERROR: Please specify issue number")
        exit(1)

    try:
        issue_no = int(issue_no)
    except ValueError:
        print(f"ERROR: Invalid issue number {issue_no}")
        exit(1)

    data = base64.b64decode(data.replace("@", "\n").encode()).decode()
    doc = json.loads(data)
    doc["issue"] = issue_no
    index = doc.pop("index")
    if index not in ("relval", "build", "utest"):
        print(f"ERROR: Invalid index", index)
        exit(1)

    index_document(index, doc)


if __name__ == "__main__":
    main()
