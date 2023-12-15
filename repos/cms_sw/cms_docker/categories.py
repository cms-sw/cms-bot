from os.path import join
_default_bot_dir = "/".join(__file__.split("/")[0:-4])
exec(open(join(_default_bot_dir, "categories.py")).read())

CMSSW_CONTAINERS = [
    "cc7",
    "cc8",
    "cms",
    "cmssw",
    "cs8",
    "cs9",
    "docker-lxr",
    "docker-vtune",
    "el8",
    "el9",
    "rocky8",
    "slc5",
    "slc6",
    "ubi8",
]

CMSSW_LABELS = {}
for item in CMSSW_CONTAINERS:
    CMSSW_LABELS[item] = [ item + "/" ]
