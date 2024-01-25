_file_items = __file__.split("/")
_default_bot_dir = "/".join(_file_items[0:-4])
exec(open("%s/%s" % (_default_bot_dir, _file_items[-1])).read())

from categories import CMSSW_CONTAINERS

for data in CMSSW_CONTAINERS:
    TYPE_COMMANDS[data] = [LABEL_COLORS["doc"], data, "mtype"]

for arch in ["x86_64", "ppc64le", "aarch64"]:
    TYPE_COMMANDS[arch] = [LABEL_COLORS["doc"], "%s-[0-9a-f]+" % arch, "mtype", True]
    TYPE_COMMANDS[arch + "-cms-docker"] = [
        LABEL_COLORS["doc"],
        "%s-([a-z]+-|)(queued|building|done|error)" % arch,
        "mtype",
        True,
        "state",
    ]
