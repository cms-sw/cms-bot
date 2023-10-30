"""
Logic to take care of imports depending on the python version
"""
import sys

if sys.version_info[0] == 2:
    # python 2 modules
    from commands import getstatusoutput as run_cmd
    from commands import getstatusoutput, getoutput
    from httplib import HTTPSConnection

    # urllib
    from urllib import urlencode, quote_plus, quote, unquote
    from urllib2 import (
        Request,
        urlopen,
        HTTPSHandler,
        build_opener,
        install_opener,
        unquote,
        HTTPError,
        HTTPPasswordMgrWithDefaultRealm,
        HTTPBasicAuthHandler,
        HTTPCookieProcessor,
    )
    from urlparse import urlparse
    from cookielib import CookieJar
else:
    # python 3 modules
    from subprocess import getstatusoutput as run_cmd
    from subprocess import getstatusoutput, getoutput
    from http.client import HTTPSConnection

    # urllib
    from urllib.parse import urlencode, quote_plus, quote, unquote, urlparse
    from urllib.request import (
        Request,
        urlopen,
        HTTPSHandler,
        build_opener,
        install_opener,
        HTTPPasswordMgrWithDefaultRealm,
        HTTPBasicAuthHandler,
        HTTPCookieProcessor,
    )
    from urllib.error import HTTPError
    from http.cookiejar import CookieJar


def cmp_f(a, b):
    return (a > b) - (a < b)
