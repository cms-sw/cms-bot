import os

import es_utils
import base64


def index_document(index, payload):
    payload["@timestamp"] = int(time() * 1000)
    payload = json.dumps(payload)

    response = es_utils.send_payload(index + "-failures", index, None, payload)


def main():
    data = os.getenv("DATA", None)
    data = base64.b64decode(data.replace("@", "\n").encode()).decode()
    doc = json.loads(data)
    index = doc.pop("index")
    index_document(index, doc)


if __name__ == "__main__":
    main()
