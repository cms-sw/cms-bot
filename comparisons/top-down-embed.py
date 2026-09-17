#!/usr/bin/env python3
"""
Build a standalone Top-Down Compare HTML page with two embedded JSON payloads.
"""

import argparse
import json
import os
import re
import sys

VIEWER_TEMPLATE = "top_down_compare_viewer.html"


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("children"), list):
        raise RuntimeError(f"Invalid top-down JSON: {path}. Expected object with children array.")
    return payload


def sanitize(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def default_output_path(file_a, file_b):
    base_a = sanitize(os.path.splitext(os.path.basename(file_a))[0])
    base_b = sanitize(os.path.splitext(os.path.basename(file_b))[0])
    return f"{base_a}-vs-{base_b}.compare.html"


def build_viewer_html(template_path, data_a, data_b, label_a, label_b, source_label):
    with open(template_path, encoding="utf-8") as template_file:
        content = template_file.read()

    embedded_a = json.dumps(data_a).replace("</", "<\\/")
    embedded_b = json.dumps(data_b).replace("</", "<\\/")

    autoload_snippet = """
    <script id=\"embedded-top-down-a\" type=\"application/json\">%s</script>
    <script id=\"embedded-top-down-b\" type=\"application/json\">%s</script>
    <script>
      (function () {
        var nodeA = document.getElementById("embedded-top-down-a");
        var nodeB = document.getElementById("embedded-top-down-b");
        if (!nodeA || !nodeB) {
          return;
        }
        var dataA = JSON.parse(nodeA.textContent);
        var dataB = JSON.parse(nodeB.textContent);
        if (typeof loadFromObjects === "function") {
          loadFromObjects(dataA, dataB, %s, %s);
          return;
        }
        window.TOP_DOWN_COMPARE_EMBEDDED = {
          a: dataA,
          b: dataB,
          labelA: %s,
          labelB: %s,
          source: %s
        };
      })();
    </script>
""" % (
        embedded_a,
        embedded_b,
        json.dumps(label_a),
        json.dumps(label_b),
        json.dumps(label_a),
        json.dumps(label_b),
        json.dumps(source_label),
    )

    if "</body>" not in content:
        raise RuntimeError(f"Template does not contain </body>: {template_path}")

    return content.replace("</body>", autoload_snippet + "</body>", 1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a standalone top-down comparison HTML with embedded JSON payloads."
    )
    parser.add_argument("file_a", help="Path to top-down JSON A")
    parser.add_argument("file_b", help="Path to top-down JSON B")
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Output HTML path (default: derived from input names)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    data_a = load_json(args.file_a)
    data_b = load_json(args.file_b)

    script_dir = os.path.dirname(os.path.realpath(__file__))
    template_path = os.path.join(script_dir, VIEWER_TEMPLATE)

    if not os.path.isfile(template_path):
        raise RuntimeError(f"Template not found: {template_path}")

    label_a = os.path.basename(args.file_a)
    label_b = os.path.basename(args.file_b)
    source_label = f"embedded top-down compare: {label_a} vs {label_b}"

    html = build_viewer_html(template_path, data_a, data_b, label_a, label_b, source_label)

    output_path = args.output or default_output_path(args.file_a, args.file_b)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(html)

    print(f"Wrote standalone compare HTML: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
