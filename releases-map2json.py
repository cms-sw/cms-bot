#!/usr/bin/env python3
import re
import json
import sys
from collections import defaultdict, OrderedDict

def parse_line(line):
    entry = {}
    for kv in line.strip().split(";"):
        if not kv:
            continue
        if "=" in kv:
            k, v = kv.split("=", 1)
            entry[k.strip()] = v.strip()
    return entry

def normalize_label(label: str):
    """Extract (major, minor, patch, pre, patchN, extra_flavor) for sorting."""
    m = re.match(r"CMSSW_(\d+)_(\d+)_(\d+)(?:_(.*))?", label)
    if not m:
        return None
    major, minor, rev, rest = m.groups()
    major, minor, rev = int(major), int(minor), int(rev)
    pre = None
    patch = None
    flavor_tokens = []
    if rest:
        tokens = rest.split("_")
        for t in tokens:
            if re.match(r"^pre\d+$", t):
                pre = int(t[3:])
            elif "patch" in t.lower():
                m2 = re.search(r"patch(\d+)", t, re.IGNORECASE)
                patch = int(m2.group(1)) if m2 else 0
            else:
                flavor_tokens.append(t)
    return (major, minor, rev,
            pre if pre is not None else float("inf"),
            patch if patch is not None else -1,
            "_".join(flavor_tokens))

def release_sort_key(label: str):
    key = normalize_label(label)
    if key is None:
        return (float("inf"), float("inf"), float("inf"), float("inf"), float("inf"), "")
    return key

def detect_flavor(label: str) -> str:
    """Detect flavor token after CMSSW_<maj>_<min>_<rev>."""
    if not label.startswith("CMSSW_"):
        return None
    rest = label[len("CMSSW_"):]
    tokens = rest.split("_")
    if len(tokens) < 3:
        return "DEFAULT"

    suffix_tokens = tokens[3:]
    for t in suffix_tokens:
        up = t.upper()
        if re.match(r"^PRE\d+$", up):
            continue
        if "PATCH" in up:
            continue
        if re.match(r"^HLT\d*$", up):
            return "HLT"
        if re.match(r"^SLHC\d*$", up):
            return "SLHC"
        if re.match(r"^UL\d*$", up):
            return "UL"
        if re.match(r"^ROOT\d*$", up):
            return up  # e.g. ROOT6
        if re.match(r"^POSTLS\d+", up):
            return "PostLS"
        return t
    return "DEFAULT"

def major_minor(label: str) -> str:
    m = re.match(r"(CMSSW_\d+_\d+)", label)
    return m.group(1) if m else "CMSSW_UNKNOWN"

def major_minor_sort_key(mm: str):
    m = re.match(r"CMSSW_(\d+)_(\d+)", mm)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (float("inf"), float("inf"))

def build_structure(filename="./releases.map"):
    data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(list)
                )
            )
        )
    )

    with open(filename) as f:
        for line in f:
            entry = parse_line(line)
            if not entry:
                continue
            label = entry.get("label")
            state = entry.get("state")
            if not label or not label.startswith("CMSSW_"):
                continue
            if state == "IB":
                continue

            type_ = entry.get("type", "Unknown")
            prodarch = "prodarch" if entry.get("prodarch") == "1" else "non-prodarch"
            flavor = detect_flavor(label)
            majmin = major_minor(label)

            arch_entry = {k: (int(v) if k == "prodarch" else v)
                          for k, v in entry.items()
                          if k not in ("label", "type", "state")}

            found = False
            for rel in data[state][prodarch][type_][flavor][majmin]:
                if rel["label"] == label:
                    rel["architectures"].append(arch_entry)
                    found = True
                    break
            if not found:
                data[state][prodarch][type_][flavor][majmin].append({
                    "label": label,
                    "architectures": [arch_entry]
                })

    # Sort releases inside each major_minor bucket
    for state in data:
        for prodarch in data[state]:
            for type_ in data[state][prodarch]:
                for flavor in data[state][prodarch][type_]:
                    for majmin in data[state][prodarch][type_][flavor]:
                        data[state][prodarch][type_][flavor][majmin].sort(
                            key=lambda x: release_sort_key(x["label"])
                        )

    # Convert to OrderedDict with stable key order
    def order_dict(d):
        if isinstance(d, dict):
            if set(d.keys()) & {"prodarch", "non-prodarch"}:
                keys = ["prodarch", "non-prodarch"]
                keys = [k for k in keys if k in d]
            elif set(d.keys()) & {"Production", "Development", "Unknown"}:
                keys = sorted(d.keys())
            elif all(re.match(r"CMSSW_\d+_\d+", k) for k in d.keys() if isinstance(k, str)):
                keys = sorted(d.keys(), key=major_minor_sort_key)
            elif "DEFAULT" in d:
                # flavors: DEFAULT first, then alphabetical
                others = sorted([k for k in d.keys() if k != "DEFAULT"])
                keys = ["DEFAULT"] + others
            else:
                keys = sorted(d.keys())
            return OrderedDict((k, order_dict(v)) for k, v in d.items())
        elif isinstance(d, list):
            return [order_dict(x) for x in d]
        return d

    return order_dict(data)

if __name__ == "__main__":
    structure = build_structure(sys.argv[1])
    print(json.dumps(structure, indent=2))

