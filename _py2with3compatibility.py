"""
Logic to take care of imports depending on the python version
"""

import sys

if sys.version_info[0] == 2:
    # python 2 modules
    # urllib
    from urllib import quote, quote_plus, unquote, urlencode

    from commands import getoutput, getstatusoutput
    from commands import getstatusoutput as run_cmd
    from cookielib import CookieJar
    from httplib import HTTPSConnection
    from urllib2 import (
        HTTPBasicAuthHandler,
        HTTPCookieProcessor,
        HTTPError,
        HTTPPasswordMgrWithDefaultRealm,
        HTTPSHandler,
        Request,
        build_opener,
        install_opener,
        urlopen,
    )
    from urlparse import urlparse
else:
    # python 3 modules
    from http.client import HTTPSConnection
    from http.cookiejar import CookieJar
    from subprocess import getoutput, getstatusoutput
    from subprocess import getstatusoutput as run_cmd
    from urllib.error import HTTPError

    # urllib
    from urllib.parse import quote, quote_plus, unquote, urlencode, urlparse
    from urllib.request import (
        HTTPBasicAuthHandler,
        HTTPCookieProcessor,
        HTTPPasswordMgrWithDefaultRealm,
        HTTPSHandler,
        Request,
        build_opener,
        install_opener,
        urlopen,
    )


def cmp_f(a, b):
    return (a > b) - (a < b)
