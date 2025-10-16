_file_items = __file__.split("/")
_default_bot_dir = "/".join(_file_items[0:-4])
exec(open("%s/%s" % (_default_bot_dir, _file_items[-1])).read())

# Override default issue trackers for cms-docker repo
# Only notify CMS_SDT members
CMSSW_ISSUES_TRACKERS = CMS_SDT[:]

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
    "el10",
    "rocky8",
    "slc5",
    "slc6",
    "ubi8",
]

CMSSW_DOCKER_LABELS = {}
for item in CMSSW_CONTAINERS:
    CMSSW_DOCKER_LABELS[item] = [item + "/"]

CMSSW_LABELS = {"cms-docker": CMSSW_DOCKER_LABELS}
