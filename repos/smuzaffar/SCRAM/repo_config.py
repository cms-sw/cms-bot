from os.path import basename, dirname, abspath

CONFIG_DIR = dirname(abspath(__file__))
GITHUB_WEBHOOK_TOKEN = "U2FsdGVkX1+8ckT0H3wKIUb59hZQrF5PZ2VlBxYyFek="
RUN_DEFAULT_CMS_BOT = False

VALID_WEB_HOOKS = [".*"]
WEBHOOK_PAYLOAD = True
JENKINS_SERVER = "http://cmsjenkins11.cern.ch:8080/dmwm-jenkins"
