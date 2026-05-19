WARN_THRESHOLD = 10.0
ERROR_THRESHOLD = 90.0
import os

CMSSW_VERSION = os.environ.get("CMSSW_VERSION")
if CMSSW_VERSION == "":
    CMSSW_VERSION = os.environ("RELEASE_FORMAT")
if CMSSW_VERSION != "":
    parts = CMSSW_VERSION.split("_")
    major = int(parts[1]) if parts[1].isdigit() else 0
    minor = int(parts[2]) if parts[2].isdigit() else 0
    CMSSW_VER = major * 100 + minor * 10
    if CMSSW_VER >= 1700:
        ERROR_THRESHOLD = 10.0
