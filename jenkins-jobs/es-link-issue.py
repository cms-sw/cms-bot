import os

import es_utils
import base64


def main():
    data = os.getenv("DATA", None)
    data = base64.b64decode(data.replace("@", "\n").encode()).decode()
    doc = json.loads(data)
    index = doc.pop("index")
    doc["@timestamp"] = int(time() * 1000)
    payload = json.dumps(doc)
    es_utils.send_payload(index + "-failures", index, None, payload)


if __name__ == "__main__":
    main()
