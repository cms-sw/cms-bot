_file_items = __file__.split("/")
_default_bot_dir = "/".join(_file_items[0:-4])
exec(open("%s/%s" % (_default_bot_dir, _file_items[-1])).read())

CONFIG_DIR = _default_bot_dir
CHECK_DPG_POG = False
