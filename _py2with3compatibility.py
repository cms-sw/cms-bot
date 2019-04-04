"""
Logic to take care of imports depending on the version
"""
import sys
if sys.version_info[0] == 2:
    # python 2 modules
    from commands import getstatusoutput as run_cmd
    from commands import getstatusoutput
    from httplib import HTTPSConnection
    from urllib import urlencode
else:
    # python 3 modules
    from subprocess import getstatusoutput as run_cmd
    from subprocess import getstatusoutput
    from urllib.parse import urlencode
    from http.client import HTTPSConnection
