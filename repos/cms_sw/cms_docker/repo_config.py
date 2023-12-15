from os.path import join

_default_bot_dir = "/".join(__file__.split("/")[0:-4])
exec(open(join(_default_bot_dir, "repo_config.py")).read())

CONFIG_DIR = _default_bot_dir
CHECK_DPG_POG = False
