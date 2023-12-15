_file_items = __file__.split("/")
_default_bot_dir = "/".join(_file_items[0:-4])
exec(open("%s/%s" % (_default_bot_dir, _file_items[-1])).read())

for arch in ["x86_64", "ppc64le", "aarch64"]:
  TYPE_COMMANDS[arch] = [LABEL_COLORS["doc"], "%s-[0-9]+", "mtype", True]
