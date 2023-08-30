from os.path import basename,dirname,abspath

CONFIG_DIR=dirname(abspath(__file__))
GH_REPO_ORGANIZATION=basename(dirname(CONFIG_DIR))
GITHUB_WEBHOOK_TOKEN='U2FsdGVkX1+8ckT0H3wKIUb59hZQrF5PZ2VlBxYyFek='

VALID_WEB_HOOKS=['.*']
USERS_TO_TRIGGER_HOOKS= set([GH_REPO_ORGANIZATION])
WEBHOOK_PAYLOAD=True
JENKINS_SERVER="http://cmsjenkins04.cern.ch:8080/cms-jenkins"
