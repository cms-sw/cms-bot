"""
Logic to take care of imports depending on the python version
"""
import sys
if sys.version_info[0] == 2:
    # python 2 modules
    from commands import getstatusoutput as run_cmd
    from commands import getstatusoutput
    from urllib import urlencode, quote_plus, quote
    from httplib import HTTPSConnection
    from urllib2 import Request, urlopen, error

else:
    # python 3 modules
    from subprocess import getstatusoutput as run_cmd
    from subprocess import getstatusoutput
    from urllib.parse import urlencode, quote_plus, quote
    from http.client import HTTPSConnection
    from urllib.request import Request, urlopen
