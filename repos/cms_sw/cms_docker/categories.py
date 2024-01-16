_file_items = __file__.split("/")
_default_bot_dir = "/".join(_file_items[0:-4])
exec(open("%s/%s" % (_default_bot_dir, _file_items[-1])).read())

CMSSW_CONTAINERS = [
    "alma8",
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
    CMSSW_LABELS[item] = [item + "/"]
