from _py2with3compatibility import (
    Request,
    urlopen,
    urlencode,
    build_opener,
    install_opener,
    CookieJar,
    HTTPCookieProcessor,
    HTTPError,
)
from json import loads


def update_crumb(jenkins_url, headers):
    try:
        req = Request(url=jenkins_url + "/crumbIssuer/api/json", headers=headers)
        crumb = loads(urlopen(req).read())
        headers[crumb["crumbRequestField"]] = crumb["crumb"]
        print("OK crumbRequest")
    except HTTPError as e:
        print("Running without Crumb Issuer: %s" % e)
        pass
    return headers


def build_jobs(jenkins_url, jobs_data, headers={}, user="cmssdt"):
    for rk in ["OIDC_CLAIM_CERN_UPN"]:
        if rk not in headers:
            headers[rk] = user
    install_opener(build_opener(HTTPCookieProcessor(CookieJar())))
    for prams, job in jobs_data:
        if not job:
            continue
        headers = update_crumb(jenkins_url, headers)
        url = jenkins_url + "/job/" + job + "/build"
        data = {"json": prams, "Submit": "Build"}
        try:
            data = urlencode(data).encode()
            req = Request(url=url, data=data, headers=headers)
            content = urlopen(req).read()
            print("ALL_OK")
        except Exception as e:
            print("Unable to start jenkins job: %s" % e)
