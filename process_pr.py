from __future__ import print_function
from categories import CMSSW_CATEGORIES, CMSSW_L2, CMSSW_L1, TRIGGER_PR_TESTS, CMSSW_ISSUES_TRACKERS, PR_HOLD_MANAGERS, EXTERNAL_REPOS,CMSDIST_REPOS, external_to_package
from releases import RELEASE_BRANCH_MILESTONE, RELEASE_BRANCH_PRODUCTION, RELEASE_BRANCH_CLOSED, CMSSW_DEVEL_BRANCH
from releases import RELEASE_MANAGERS, SPECIAL_RELEASE_MANAGERS
from cms_static import VALID_CMSDIST_BRANCHES, NEW_ISSUE_PREFIX, NEW_PR_PREFIX, ISSUE_SEEN_MSG, BUILD_REL, GH_CMSSW_REPO, GH_CMSDIST_REPO, CMSBOT_IGNORE_MSG, VALID_CMS_SW_REPOS_FOR_TESTS
from cms_static import BACKPORT_STR,GH_CMSSW_ORGANIZATION
from repo_config import GH_REPO_ORGANIZATION
import re, time
from datetime import datetime
from os.path import join, exists
from os import environ
from github_utils import get_token, edit_pr, api_rate_limits
from socket import setdefaulttimeout
from _py2with3compatibility import run_cmd

try: from categories import COMMENT_CONVERSION
except: COMMENT_CONVERSION={}
setdefaulttimeout(300)
CMSDIST_REPO_NAME=join(GH_REPO_ORGANIZATION, GH_CMSDIST_REPO)
CMSSW_REPO_NAME=join(GH_REPO_ORGANIZATION, GH_CMSSW_REPO)

# Prepare various comments regardless of whether they will be made or not.
def format(s, **kwds): return s % kwds

TRIGERING_TESTS_ABORT_MSG = 'Jenkins tests are aborted.'
TRIGERING_TESTS_MSG = 'The tests are being triggered in jenkins.'
TRIGERING_TESTS_MSG1 = 'Jenkins tests started for '
TRIGERING_CODE_CHECK_MSG = 'The code-checks are being triggered in jenkins.'
TRIGERING_STYLE_TEST_MSG = 'The project style tests are being triggered in jenkins.'
IGNORING_TESTS_MSG = 'Ignoring test request.'
TESTS_RESULTS_MSG = '^\s*([-|+]1|I had the issue.*)\s*$'
FAILED_TESTS_MSG = 'The jenkins tests job failed, please try again.'
PUSH_TEST_ISSUE_MSG='^\[Jenkins CI\] Testing commit: [0-9a-f]+$'
HOLD_MSG = "Pull request has been put on hold by "
#Regexp to match the test requests
WF_PATTERN="[1-9][0-9]*(\.[0-9]+|)"
CMSSW_QUEUE_PATTERN='CMSSW_[0-9]+_[0-9]+_([A-Z][A-Z0-9]+_|)X'
ARCH_PATTERN='[a-z0-9]+_[a-z0-9]+_[a-z0-9]+'
CMSSW_RELEASE_QUEUE_PATTERN=format('(%(cmssw)s|%(arch)s|%(cmssw)s/%(arch)s)', cmssw=CMSSW_QUEUE_PATTERN, arch=ARCH_PATTERN)
CLOSE_REQUEST=re.compile('^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)close\s*$',re.I)
CMS_PR_PATTERN=format('(#[1-9][0-9]*|(%(cmsorgs)s)/+[a-zA-Z0-9_-]+#[1-9][0-9]*|https://+github.com/+(%(cmsorgs)s)/+[a-zA-Z0-9_-]+/+pull/+[1-9][0-9]*)',
                      cmsorgs='|'.join(EXTERNAL_REPOS))
TEST_REGEXP = format("^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)test(\s+workflow(s|)\s+(%(workflow)s(\s*,\s*%(workflow)s|)*)|)(\s+with\s+(%(cms_pr)s(\s*,\s*%(cms_pr)s)*)|)(\s+for\s+%(release_queue)s|)\s*$",
                     workflow=WF_PATTERN,
                     cms_pr=CMS_PR_PATTERN,
                     release_queue=CMSSW_RELEASE_QUEUE_PATTERN)

REGEX_TEST_REG = re.compile(TEST_REGEXP, re.I)
REGEX_TEST_ABORT = re.compile("^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)abort(\s+test|)$", re.I)
TEST_WAIT_GAP=720
ALL_CHECK_FUNCTIONS = None
MULTILINE_COMMENTS_MAP = {
              "workflow(s|)":     [format('^\s*%(workflow)s(\s*,\s*%(workflow)s|)*\s*$', workflow= WF_PATTERN), "MATRIX_EXTRAS"],
              "pull_request(s|)": [format('%(cms_pr)s(\s*,\s*%(cms_pr)s)*', cms_pr=CMS_PR_PATTERN ),            "PULL_REQUESTS"],
              "full_cmssw":       ['true|false',                                                                "BUILD_FULL_CMSSW"],
              "dry_run":          ['true|false',                                                                "DRY_RUN"],
              "jenkins_slave":    ['[a-zA-Z][a-zA-Z0-9_-]+' ,                                                   "RUN_ON_SLAVE"],
              "(arch(itecture(s|))|release|release/arch)" : [ CMSSW_RELEASE_QUEUE_PATTERN,                      "RELEASE_FORMAT"],
              "enable_test(s|)":  ["gpu",                                                                       "ENABLE_BOT_TESTS"],
              "ignore_test(s|)":  ["build-warnings|clang-warnings",                                             "IGNORE_BOT_TESTS"]
              }

def get_last_commit(pr):
  last_commit = None
  try:
    # This requires at least PyGithub 1.23.0. Making it optional for the moment.
    last_commit = pr.get_commits().reversed[0].commit
  except:
    # This seems to fail for more than 250 commits. Not sure if the
    # problem is github itself or the bindings.
    try:
      last_commit = pr.get_commits()[pr.commits - 1].commit
    except IndexError:
      print("Index error: May be PR with no commits")
  return last_commit

#Read a yaml file
def read_repo_file(repo_config, repo_file, default=None):
  import yaml
  file_path = join(repo_config.CONFIG_DIR, repo_file)
  contents = default
  if exists(file_path):
    contents = (yaml.load(file(file_path)))
    if not contents: contents = default
  return contents

#
# creates a properties file to trigger the test of the pull request
#

def create_properties_file_tests(repository, pr_number, parameters, dryRun, abort=False, req_type="tests", repo_config=None):
  if abort: req_type = "abort"
  repo_parts = repository.split("/")
  if (req_type in "tests"):
    try:
      if (not repo_parts[0] in EXTERNAL_REPOS): req_type = "user-"+req_type
      elif not repo_config.CMS_STANDARD_TESTS: req_type = "user-"+req_type
    except: pass
  out_file_name = 'trigger-%s-%s-%s.properties' % (req_type, repository.replace("/","-"), pr_number)
  parameters['USE_MULTIPLE_PRS_JOB']='true'

  try:
    if repo_config.JENKINS_SLAVE_LABEL: parameters['RUN_LABEL']=repo_config.JENKINS_SLAVE_LABEL
  except: pass
  print('PropertyFile: ',out_file_name)
  print('Data:',parameters)
  create_property_file(out_file_name, parameters, dryRun)

def create_property_file(out_file_name,parameters, dryRun):
  if dryRun:
    print('Not creating cleanup properties file (dry-run): %s' % out_file_name)
    return
  print('Creating properties file %s' % out_file_name)
  out_file = open(out_file_name , 'w' )
  for k in parameters: out_file.write( '%s=%s\n' % (k,parameters[k]))
  out_file.close()

# Update the milestone for a given issue.
def updateMilestone(repo, issue, pr, dryRun):
  milestoneId = RELEASE_BRANCH_MILESTONE.get(pr.base.label.split(":")[1], None)
  if not milestoneId:
    print("Unable to find a milestone for the given branch")
    return
  if pr.state != "open":
    print("PR not open, not setting/checking milestone")
    return
  if issue.milestone and issue.milestone.id==milestoneId: return
  milestone = repo.get_milestone(milestoneId)
  print("Setting milestone to %s" % milestone.title)
  if dryRun: return
  issue.edit(milestone=milestone)

def find_last_comment(issue, user, match):
  last_comment = None
  for comment in issue.get_comments():
    if (user != comment.user.login) or (not comment.body):
      continue
    if not re.match(match,comment.body.encode("ascii", "ignore").strip("\n\t\r "),re.MULTILINE):
      continue
    last_comment = comment
    print("Matched comment from ",comment.user.login+" with comment id ",comment.id)
  return last_comment

def modify_comment(comment, match, replace, dryRun):
  comment_msg = comment.body.encode("ascii", "ignore") if comment.body else ""
  if match:
    new_comment_msg = re.sub(match,replace,comment_msg)
  else:
    new_comment_msg = comment_msg+"\n"+replace
  if new_comment_msg != comment_msg:
    if not dryRun:
      comment.edit(new_comment_msg)
      print("Message updated")
  return 0

def get_assign_categories(line):
  m = re.match("^\s*(New categories assigned:\s*|unassign\s+|assign\s+)([a-z0-9,\s]+)\s*$", line, re.I)
  if m:
    assgin_type = m.group(1).lower()
    new_cats = []
    for ex_cat in m.group(2).replace(" ","").split(","):
      if (not ex_cat in CMSSW_CATEGORIES): continue
      new_cats.append(ex_cat)
    return (assgin_type.strip(), new_cats)
  return ('', [])

def ignore_issue(repo_config, repo, issue):
  if issue.number in repo_config.IGNORE_ISSUES: return True
  if (repo.full_name in repo_config.IGNORE_ISSUES) and (issue.number in repo_config.IGNORE_ISSUES[repo.full_name]):
    return True
  if re.match(BUILD_REL, issue.title):
    return True
  if issue.body:
    if re.match(CMSBOT_IGNORE_MSG, issue.body.encode("ascii", "ignore").split("\n",1)[0].strip() ,re.I):
      return True
  return False

def check_extra_labels(first_line, extra_labels):
  if "bug" in first_line:
    extra_labels["type"]=["bug-fix"]
  elif "feature" in first_line:
    extra_labels["type"]=["new-feature"]
  elif "urgent" in first_line:
    extra_labels["urgent"]=["urgent"]
  elif "backport" in first_line:
    bp_pr = ""
    if "#" in first_line: bp_pr = first_line.split("#",1)[1].strip()
    else: bp_pr = first_line.split("/pull/",1)[1].strip("/").strip()
    extra_labels["backport"]=["backport", bp_pr]

def check_ignore_bot_tests(first_line, *args):
  return first_line.upper().replace(" ","")

def check_enable_bot_tests(first_line, *args):
  return first_line.upper().replace(" ","")

def check_pull_requests(first_line, repo, *args):
  return " ".join(get_prs_list_from_string(first_line, repo))

def check_release_format(first_line, repo, params, *args):
  rq = first_line
  ra = ''
  if '/' in rq:
    rq, ra = rq.split('/',1)
  elif re.match('^'+ARCH_PATTERN+'$', rq):
    ra = rq
    rq = ''
  params['ARCHITECTURE_FILTER'] = ra
  return rq

def check_test_cmd(first_line, repo):
  m = REGEX_TEST_REG.match(first_line)
  if m:
    wfs = ""
    prs= []
    cmssw_que = ""
    print(m.groups())
    if m.group(6): wfs = ",".join(set(m.group(6).replace(" ","").split(",")))
    if m.group(11): prs = get_prs_list_from_string(m.group(11), repo)
    if m.group(20): cmssw_que = m.group(20)
    return (True, " ".join(prs), wfs, cmssw_que)
  return (False, "", "", "")

def get_prs_list_from_string(pr_string="", repo_string=""):
  prs = []
  for pr in [x.strip().split('/github.com/',1)[-1].replace('/pull/','#').strip('/') for x in pr_string.split(",") if x.strip()]:
    while '//' in pr: pr = pr.replace('//','/')
    if pr.startswith('#'): pr = repo_string+pr
    prs.append(pr)
  return prs

def parse_extra_params(full_comment, repo):
  global ALL_CHECK_FUNCTIONS
  error_lines = []
  matched_extra_args = {}
  if ALL_CHECK_FUNCTIONS is None:
    all_globals = globals()
    ALL_CHECK_FUNCTIONS = dict([(f,all_globals[f]) for f in all_globals if f.startswith('check_') and callable(all_globals[f])])
  for l in full_comment[1:]:
    l = l.replace(' ', '')
    if l.startswith('-'): l = l[1:]
    if l=='': continue
    if not '=' in l:
      error_lines.append('"=" not found in line arg: ' + l)
      continue

    for k, pttrn in MULTILINE_COMMENTS_MAP.items():
      line_args = l.split('=', 1)
      if not re.match(k, line_args[0], re.I): continue
      if not re.match(pttrn[0], line_args[1], re.I):
        error_lines.append('Invalid value "%s" for parameter "%s" used.' % (line_args[1], line_args[0]))
        break
      try:
        func = 'check_%s' % pttrn[1].lower()
        if func in ALL_CHECK_FUNCTIONS:
          line_args[1] = ALL_CHECK_FUNCTIONS[func](line_args[1], repo, matched_extra_args)
      except:
        pass
      matched_extra_args[pttrn[1]] = line_args[1]
      break
  if error_lines:
    matched_extra_args = {"errors" : error_lines}
  return matched_extra_args

def multiline_check_function(first_line, comment_lines, repository):
  if not "test parameters" in first_line.lower():
    return False, {}
  extra_params = parse_extra_params(comment_lines, repository)
  print(extra_params)
  if 'errors' in extra_params: return False, {}
  return True, extra_params

def get_changed_files(repo, pr, use_gh_patch=False):
  if (not use_gh_patch) and (pr.changed_files<=300): return [f.filename for f in pr.get_files()]
  cmd="curl -s -L https://patch-diff.githubusercontent.com/raw/%s/pull/%s.patch | grep '^diff --git ' | sed 's|.* a/||;s|  *b/.*||' | sort | uniq" % (repo.full_name,pr.number)
  e , o = run_cmd(cmd)
  if e: return []
  return o.split("\n")

def get_backported_pr(msg):
  if BACKPORT_STR in msg:
    bp_num=msg.split(BACKPORT_STR,1)[-1].split("\n",1)[0].strip()
    if re.match("^[1-9][0-9]*$",bp_num): return bp_num
  return ""

def cmssw_file2Package(repo_config, filename):
  try:
    return repo_config.file2Package(filename)
  except:
    return "/".join(filename.split("/", 2)[0:2])

def get_jenkins_job(issue):
  test_line=""
  for line in [l.strip() for l in issue.body.encode("ascii", "ignore").split("\n")]:
    if line.startswith("Build logs are available at:"): test_line=line
  if test_line:
    test_line=test_line.split("Build logs are available at: ",1)[-1].split("/")
    if test_line[-4]=="job" and test_line[-1]=="console":
      return test_line[-3],test_line[-2]
  return "",""

def process_pr(repo_config, gh, repo, issue, dryRun, cmsbuild_user=None, force=False):
  if (not force) and ignore_issue(repo_config, repo, issue): return
  api_rate_limits(gh)
  prId = issue.number
  repository = repo.full_name
  repo_org, repo_name = repository.split("/",1)
  if not cmsbuild_user: cmsbuild_user=repo_config.CMSBUILD_USER
  print("Working on ",repo.full_name," for PR/Issue ",prId,"with admin user",cmsbuild_user)
  cmssw_repo = (repo_name==GH_CMSSW_REPO)
  cms_repo = (repo_org in EXTERNAL_REPOS)
  external_repo = (repository!=CMSSW_REPO_NAME) and (len([e for e in EXTERNAL_REPOS if repo_org==e])>0)
  create_test_property = False
  repo_cache = {repository: repo}
  packages = set([])
  add_external_category = False
  signing_categories = set([])
  new_package_message = ""
  mustClose = False
  releaseManagers = []
  signatures = {}
  watchers = []
  #Process Pull Request
  pkg_categories = set([])
  REGEX_EX_CMDS="^type\s+(bug(-fix|fix|)|(new-|)feature)|urgent|backport\s+(of\s+|)(#|http(s|):/+github\.com/+%s/+pull/+)\d+$" % (repo.full_name)
  known_ignore_tests=MULTILINE_COMMENTS_MAP["ignore_test(s|)"]
  known_enable_tests=MULTILINE_COMMENTS_MAP["enable_test(s|)"]
  REGEX_EX_IGNORE_CHKS='^ignore\s+((%s)(\s*,\s*(%s))*|none)$' % (known_ignore_tests, known_ignore_tests)
  REGEX_EX_ENABLE_TESTS='^enable\s+((%s)(\s*,\s*(%s))*|none)$' % (known_enable_tests, known_enable_tests)
  last_commit_date = None
  push_test_issue = False
  requestor = issue.user.login.encode("ascii", "ignore")
  ignore_tests = ''
  enable_tests = ''
  if issue.pull_request:
    pr   = repo.get_pull(prId)
    if pr.changed_files==0:
      print("Ignoring: PR with no files changed")
      return
    if cmssw_repo and cms_repo and (pr.base.ref == CMSSW_DEVEL_BRANCH):
      if pr.state != "closed":
        print("This pull request must go in to master branch")
        if not dryRun:
          edit_pr(get_token(gh), repo.full_name, prId, base="master")
          msg = format("@%(user)s, %(dev_branch)s branch is closed for direct updates. cms-bot is going to move this PR to master branch.\n"
                       "In future, please use cmssw master branch to submit your changes.\n",
                       user=requestor,
                       dev_branch=CMSSW_DEVEL_BRANCH)
          issue.create_comment(msg)
      return
    # A pull request is by default closed if the branch is a closed one.
    if pr.base.ref in RELEASE_BRANCH_CLOSED: mustClose = True
    # Process the changes for the given pull request so that we can determine the
    # signatures it requires.
    if cmssw_repo or not external_repo:
      if cmssw_repo:
        if (pr.base.ref=="master"): signing_categories.add("code-checks")
        updateMilestone(repo, issue, pr, dryRun)
      packages = sorted([x for x in set([cmssw_file2Package(repo_config, f)
                           for f in get_changed_files(repo, pr)])])
      print("First Package: ",packages[0])
      create_test_property = True
    else:
      add_external_category = True
      packages = set (["externals/"+repository])
      ex_pkg = external_to_package(repository)
      if ex_pkg: packages.add(ex_pkg)
      if (repo_org!=GH_CMSSW_ORGANIZATION) or (repo_name in VALID_CMS_SW_REPOS_FOR_TESTS):
          create_test_property = True
      if (repo_name == GH_CMSDIST_REPO) and (not re.match(VALID_CMSDIST_BRANCHES,pr.base.ref)):
          print("Skipping PR as it does not belong to valid CMSDIST branch")
          return

    print("Following packages affected:")
    print("\n".join(packages))
    pkg_categories = set([category for package in packages
                              for category, category_packages in list(CMSSW_CATEGORIES.items())
                              if package in category_packages])
    signing_categories.update(pkg_categories)

    # For PR, we always require tests.
    signing_categories.add("tests")
    if add_external_category: signing_categories.add("externals")
    # We require ORP approval for releases which are in production.
    # or all externals package
    if cms_repo and ((not cmssw_repo) or (pr.base.ref in RELEASE_BRANCH_PRODUCTION)):
      print("This pull request requires ORP approval")
      signing_categories.add("orp")
      for l1 in CMSSW_L1:
        if not l1 in CMSSW_L2: CMSSW_L2[l1]=[]
        if not "orp" in CMSSW_L2[l1]: CMSSW_L2[l1].append("orp")

    print("Following categories affected:")
    print("\n".join(signing_categories))

    if cmssw_repo:
      # If there is a new package, add also a dummy "new" category.
      all_packages = [package for category_packages in list(CMSSW_CATEGORIES.values())
                              for package in category_packages]
      has_category = all([package in all_packages for package in packages])
      if not has_category:
        new_package_message = "\nThe following packages do not have a category, yet:\n\n"
        new_package_message += "\n".join([package for package in packages if not package in all_packages]) + "\n"
        new_package_message += "Please create a PR for https://github.com/cms-sw/cms-bot/blob/master/categories_map.py to assign category\n"
        print(new_package_message)
        signing_categories.add("new-package")

    # Add watchers.yaml information to the WATCHERS dict.
    WATCHERS = read_repo_file(repo_config, "watchers.yaml", {})
    # Given the packages check if there are additional developers watching one or more.
    author = pr.user.login
    watchers = set([user for package in packages
                         for user, watched_regexp in list(WATCHERS.items())
                         for regexp in watched_regexp
                         if re.match("^" + regexp + ".*", package) and user != author])
    #Handle category watchers
    catWatchers = read_repo_file(repo_config, "category-watchers.yaml", {})
    for user, cats in list(catWatchers.items()):
      for cat in cats:
        if cat in signing_categories:
          print("Added ",user, " to watch due to cat",cat)
          watchers.add(user)

    # Handle watchers
    watchingGroups = read_repo_file(repo_config, "groups.yaml", {})
    for watcher in [x for x in watchers]:
      if not watcher in watchingGroups: continue
      watchers.remove(watcher)
      watchers.update(set(watchingGroups[watcher]))      
    watchers = set(["@" + u for u in watchers])
    print("Watchers " + ", ".join(watchers))

    last_commit = get_last_commit(pr)
    if last_commit is None: return
    last_commit_date = last_commit.committer.date
    print("Latest commit by ",last_commit.committer.name.encode("ascii", "ignore")," at ",last_commit_date)
    print("Latest commit message: ",last_commit.message.encode("ascii", "ignore"))
    print("Latest commit sha: ",last_commit.sha)
    print("PR update time",pr.updated_at)
    print("Time UTC:",datetime.utcnow())
    if last_commit_date>datetime.utcnow():
      print("==== Future commit found ====")
      add_labels = True
      try: add_labels = repo_config.ADD_LABELS
      except: pass
      if (not dryRun) and add_labels:
        labels = [x.name.encode("ascii", "ignore") for x in issue.labels]
        if not 'future-commit' in labels:
          labels.append('future-commit')
          issue.edit(labels=labels)
      return
    extra_rm = RELEASE_MANAGERS.get(pr.base.ref, [])
    if repository==CMSDIST_REPO_NAME:
      br = "_".join(pr.base.ref.split("/")[:2][-1].split("_")[:3])+"_X"
      if br: extra_rm=extra_rm+RELEASE_MANAGERS.get(br, [])
    releaseManagers=list(set(extra_rm+CMSSW_L1))
  else:
    try:
      if (repo_config.OPEN_ISSUE_FOR_PUSH_TESTS) and (requestor == cmsbuild_user) and re.match(PUSH_TEST_ISSUE_MSG,issue.title):
        signing_categories.add("tests")
        push_test_issue = True
    except: pass

  # Process the issue comments
  signatures = dict([(x, "pending") for x in signing_categories])
  pre_checks = ("code-checks" in signing_categories)
  already_seen = None
  pull_request_updated = False
  comparison_done = False
  comparison_notrun = False
  tests_already_queued = False
  tests_requested = False
  mustMerge = False
  trigger_test_on_signature = True
  has_categories_approval = False
  release_queue = ''
  release_arch = ''
  cmssw_prs = ''
  extra_wfs = ''
  global_test_params = {}
  assign_cats = {}
  hold = {}
  extra_labels = {}
  last_test_start_time = None
  abort_test = False
  need_external = False
  trigger_code_checks=False
  triggerred_code_checks=False
  backport_pr_num = ""
  comp_warnings = False
  extra_testers = []
  all_comments = [issue]

  #start of parsing comments section

  for c in issue.get_comments(): all_comments.append(c)
  for comment in all_comments:
    commenter = comment.user.login.encode("ascii", "ignore")
    valid_commenter = commenter in TRIGGER_PR_TESTS + list(CMSSW_L2.keys()) + CMSSW_L1 + releaseManagers + [repo_org]
    if (not valid_commenter) and (requestor!=commenter): continue
    comment_msg = comment.body.encode("ascii", "ignore") if comment.body else ""
    if (commenter in COMMENT_CONVERSION) and (comment.created_at<=COMMENT_CONVERSION[commenter]['comments_before']):
      orig_msg = comment_msg
      for cmt in COMMENT_CONVERSION[commenter]['comments']:
        comment_msg = comment_msg.replace(cmt[0],cmt[1])
      if (orig_msg != comment_msg): print("==>Updated Comment:",commenter,comment.created_at,"\n",comment_msg)
    # The first line is an invariant.
    comment_lines = [ l.strip() for l in comment_msg.split("\n") if l.strip() ]
    first_line = comment_lines[0:1]
    if not first_line: continue
    first_line = first_line[0]
    if (commenter == cmsbuild_user) and re.match(ISSUE_SEEN_MSG, first_line):
      already_seen = comment
      backport_pr_num = get_backported_pr(comment_msg)
      if issue.pull_request and last_commit_date:
        if (comment.created_at >= last_commit_date): pull_request_updated = False
        else: pull_request_updated = True
      continue

    assign_type, new_cats = get_assign_categories(first_line)
    if new_cats:
      if (assign_type == "new categories assigned:") and (commenter == cmsbuild_user):
        for ex_cat in new_cats:
          if ex_cat in assign_cats: assign_cats[ex_cat] = 1
      if ((commenter in CMSSW_L2) or (commenter in  CMSSW_ISSUES_TRACKERS + CMSSW_L1)):
        if assign_type == "assign":
          for ex_cat in new_cats:
            if not ex_cat in signing_categories:
              assign_cats[ex_cat] = 0
              signing_categories.add(ex_cat)
              signatures[ex_cat]="pending"
        elif assign_type == "unassign":
          for ex_cat in new_cats:
            if ex_cat in assign_cats:
              assign_cats.pop(ex_cat)
              signing_categories.remove(ex_cat)
              signatures.pop(ex_cat)
      continue

    # Some of the special users can say "hold" prevent automatic merging of
    # fully signed PRs.
    if re.match("^hold$", first_line, re.I):
      if commenter in CMSSW_L1 + list(CMSSW_L2.keys()) + releaseManagers + PR_HOLD_MANAGERS: hold[commenter]=1
      continue
    if re.match(REGEX_EX_CMDS, first_line, re.I):
      if commenter in CMSSW_L1 + list(CMSSW_L2.keys()) + releaseManagers + [requestor]:
        check_extra_labels(first_line.lower(), extra_labels)
      continue
    if re.match(REGEX_EX_IGNORE_CHKS, first_line, re.I):
      if commenter in CMSSW_L1 + list(CMSSW_L2.keys()) + releaseManagers:
        ignore_tests = check_ignore_bot_tests (first_line.split(" ",1)[-1])
      continue
    if re.match(REGEX_EX_ENABLE_TESTS, first_line, re.I):
      if commenter in CMSSW_L1 + list(CMSSW_L2.keys()) + releaseManagers:
        enable_tests = check_enable_bot_tests (first_line.split(" ",1)[-1])
      continue
    if re.match('^allow\s+@([^ ]+)\s+test\s+rights$',first_line, re.I):
      if commenter in CMSSW_L1 + list(CMSSW_L2.keys()) + releaseManagers:
        tester = first_line.split("@",1)[-1].split(" ",1)[0]
        if not tester in TRIGGER_PR_TESTS:
          TRIGGER_PR_TESTS.append(tester)
          extra_testers.append(tester)
          print("Added user in test category:",tester)
      continue
    if re.match("^unhold$", first_line, re.I):
      if commenter in CMSSW_L1:
        hold = {}
      elif commenter in list(CMSSW_L2.keys()) + releaseManagers + PR_HOLD_MANAGERS:
        if commenter in hold: del hold[commenter]
      continue
    if (commenter == cmsbuild_user) and (re.match("^"+HOLD_MSG+".+", first_line)):
      for u in first_line.split(HOLD_MSG,2)[1].split(","):
        u = u.strip().lstrip("@")
        if u in hold: hold[u]=0
    if CLOSE_REQUEST.match(first_line):
      if (commenter in CMSSW_L1 + list(CMSSW_L2.keys()) + releaseManagers) or \
         ((not issue.pull_request) and (commenter in  CMSSW_ISSUES_TRACKERS)):
         mustClose = True
         print("==>Closing requested received from %s" % commenter)
      continue
    if valid_commenter:
      valid_multiline_comment , test_params = multiline_check_function(first_line, comment_lines, repository)
      if valid_multiline_comment:
        global_test_params = dict(test_params)
        continue

    # Ignore all other messages which are before last commit.
    if issue.pull_request and (comment.created_at < last_commit_date):
      continue

    if ("code-checks"==first_line and cmssw_repo):
      signatures["code-checks"] = "pending"
      trigger_code_checks=True
      triggerred_code_checks=False
      print("Found:Code Checks")
      continue

    # Check for cmsbuild_user comments and tests requests only for pull requests
    if commenter == cmsbuild_user:
      if not issue.pull_request and not push_test_issue: continue
      sec_line = comment_lines[1:2]
      if not sec_line: sec_line = ""
      else: sec_line = sec_line[0]
      if re.match("Comparison is ready", first_line):
        if ('tests' in signatures) and signatures["tests"]!='pending': comparison_done = True
      elif "-code-checks" == first_line:
        signatures["code-checks"] = "rejected"
        trigger_code_checks=False
        triggerred_code_checks=False
      elif "+code-checks" == first_line:
        signatures["code-checks"] = "approved"
        trigger_code_checks=False
        triggerred_code_checks=False
      elif TRIGERING_CODE_CHECK_MSG == first_line:
        trigger_code_checks=False
        triggerred_code_checks=True
        signatures["code-checks"] = "pending"
      elif re.match("^Comparison not run.+",first_line):
        if ('tests' in signatures) and signatures["tests"]!='pending': comparison_notrun = True
      elif re.match( FAILED_TESTS_MSG, first_line) or re.match(IGNORING_TESTS_MSG, first_line):
        tests_already_queued = False
        tests_requested = False
        signatures["tests"] = "pending"
        trigger_test_on_signature = False
      elif re.match("Pull request ([^ #]+|)[#][0-9]+ was updated[.].*", first_line):
        pull_request_updated = False
      elif re.match( TRIGERING_TESTS_MSG, first_line) or re.match( TRIGERING_TESTS_MSG1, first_line):
        tests_already_queued = True
        tests_requested = False
        signatures["tests"] = "started"
        trigger_test_on_signature = False
        last_test_start_time = comment.created_at
        abort_test = False
        need_external = False
        if sec_line.startswith("Using externals from cms-sw/cmsdist#"): need_external = True
        elif sec_line.startswith('Tested with other pull request'): need_external = True
        elif sec_line.startswith('Using extra pull request'): need_external = True
      elif re.match( TESTS_RESULTS_MSG, first_line):
        test_sha = sec_line.replace("Tested at: ","").strip()
        if (not push_test_issue) and (test_sha != last_commit.sha) and (test_sha != 'UNKNOWN') and (not "I had the issue " in first_line):
          print("Ignoring test results for sha:",test_sha)
          continue
        trigger_test_on_signature = False
        tests_already_queued = False
        tests_requested = False
        comparison_done = False
        comparison_notrun = False
        comp_warnings = False
        if "+1" in first_line:
          signatures["tests"] = "approved"
          comp_warnings = len([1 for l in comment_lines if 'Compilation Warnings: Yes' in l ])>0
        elif "-1" in first_line:
          signatures["tests"] = "rejected"
        else:
          signatures["tests"] = "pending"
        print('Previous tests already finished, resetting test request state to ',signatures["tests"])
      elif re.match( TRIGERING_TESTS_ABORT_MSG, first_line):
        abort_test = False
      #continue

    if issue.pull_request or push_test_issue:
      # Check if the release manager asked for merging this.
      if (commenter in releaseManagers + CMSSW_L1) and re.match("^\s*(merge)\s*$", first_line, re.I):
        mustMerge = True
        mustClose = False
        if (commenter in CMSSW_L1) and ("orp" in signatures): signatures["orp"] = "approved"
        continue

      # Check if the someone asked to trigger the tests
      if valid_commenter:
        ok, v2, v3, v4 = check_test_cmd(first_line, repository)
        if ok:
          cmssw_prs = v2
          extra_wfs = v3
          release_queue = v4
          release_arch = ''
          if '/' in release_queue:
            release_queue, release_arch = release_queue.split('/',1)
          elif re.match('^'+ARCH_PATTERN+'$', release_queue):
            release_arch = release_queue
            release_queue = ''
          print('Tests requested:', commenter, 'asked to test this PR with cmssw_prs=%s, release_queue=%s, arch=%s and workflows=%s' % (cmssw_prs, release_queue, release_arch, extra_wfs))
          print("Comment message:",first_line)
          trigger_test_on_signature = False
          if tests_already_queued:
            print("Test results not obtained in ",comment.created_at-last_test_start_time)
            diff = time.mktime(comment.created_at.timetuple()) - time.mktime(last_test_start_time.timetuple())
            if diff>=TEST_WAIT_GAP:
              print("Looks like tests are stuck, will try to re-queue")
              tests_already_queued = False
          if not tests_already_queued:
            print('cms-bot will request test for this PR')
            tests_requested = True
            comparison_done = False
            comparison_notrun = False
            signatures["tests"] = "pending"
          else:
            print('Tests already request for this PR')
          continue
        elif (REGEX_TEST_ABORT.match(first_line) and 
              ((signatures["tests"] == "started") or 
               ((signatures["tests"] != "pending") and (not comparison_done) and (not push_test_issue)))):
          tests_already_queued = False
          abort_test = True
          signatures["tests"] = "pending"

    # Check L2 signoff for users in this PR signing categories
    if commenter in CMSSW_L2 and [x for x in CMSSW_L2[commenter] if x in signing_categories]:
      ctype = ""
      selected_cats = []
      if re.match("^([+]1|approve[d]?|sign|signed)$", first_line, re.I):
        ctype = "+1"
        selected_cats = CMSSW_L2[commenter]
      elif re.match("^([-]1|reject|rejected)$", first_line, re.I):
        ctype = "-1"
        selected_cats = CMSSW_L2[commenter]
      elif re.match("^[+-][a-z][a-z0-9]+$", first_line, re.I):
        category_name = first_line[1:].lower()
        if category_name in CMSSW_L2[commenter]:
          ctype = first_line[0]+"1"
          selected_cats = [ category_name ]
      elif re.match("^(reopen)$", first_line, re.I):
        ctype = "reopen"
      if ctype == "+1":
        for sign in selected_cats:
          signatures[sign] = "approved"
          has_categories_approval = True
          if sign == "orp": mustClose = False
      elif ctype == "-1":
        for sign in selected_cats:
          signatures[sign] = "rejected"
          has_categories_approval = False
          if sign == "orp": mustClose = False
      elif ctype == "reopen":
        if "orp" in CMSSW_L2[commenter]:
          signatures["orp"] = "pending"
          mustClose = False
      continue

  # end of parsing comments section

  if push_test_issue:
    auto_close_push_test_issue = True
    try: auto_close_push_test_issue=repo_config.AUTO_CLOSE_PUSH_TESTS_ISSUE
    except: pass
    if auto_close_push_test_issue and (issue.state == "open") and ('tests' in signatures) and ((signatures["tests"] in ["approved","rejected"]) or abort_test):
      print("Closing the issue as it has been tested/aborted")
      if not dryRun: issue.edit(state="closed")
    if abort_test:
      job, bnum = get_jenkins_job(issue)
      if job and bnum:
        params = {}
        params["JENKINS_PROJECT_TO_KILL"]=job
        params["JENKINS_BUILD_NUMBER"]=bnum
        create_property_file("trigger-abort-%s" % job, params, dryRun)
    return

  is_hold = len(hold)>0
  new_blocker = False
  blockers = ""
  for u in hold:
    blockers += " @"+u+","
    if hold[u]: new_blocker = True
  blockers = blockers.rstrip(",")

  new_assign_cats = []
  for ex_cat in assign_cats:
    if assign_cats[ex_cat]==1: continue
    new_assign_cats.append(ex_cat)

  print("All assigned cats:",",".join(list(assign_cats.keys())))
  print("Newly assigned cats:",",".join(new_assign_cats))
  print("Ignore tests:",ignore_tests)
  print("Enable tests:",enable_tests)
  print("Tests: %s" % (cmssw_prs))

  # Labels coming from signature.
  labels = []
  for cat in signing_categories:
    l = cat+"-pending"
    if cat in signatures: l = cat+"-"+signatures[cat]
    labels.append(l)

  if not issue.pull_request and len(signing_categories)==0:
    labels.append("pending-assignment")
  # Additional labels.
  if is_hold: labels.append("hold")

  dryRunOrig = dryRun
  if pre_checks and ((not already_seen) or pull_request_updated):
    for cat in ["code-checks"]:
      if (cat in signatures) and (signatures[cat]!="approved"):
        dryRun=True
        break

  old_labels = set([x.name.encode("ascii", "ignore") for x in issue.labels])
  print("Stats:",backport_pr_num,extra_labels)
  print("Old Labels:",sorted(old_labels))
  print("Compilation Warnings: ",comp_warnings)
  if "backport" in extra_labels:
    if backport_pr_num!=extra_labels["backport"][1]:
      try:
        bp_pr = repo.get_pull(int(extra_labels["backport"][1]))
        backport_pr_num=extra_labels["backport"][1]
        if bp_pr.merged: extra_labels["backport"][0]="backport-ok"
      except Exception as e :
        print("Error: Unknown PR", backport_pr_num,"\n",e)
        backport_pr_num=""
        extra_labels.pop("backport")

      if already_seen:
        if dryRun: print("Update PR seen message to include backport PR number",backport_pr_num)
        else:
          new_msg = ""
          for l in already_seen.body.encode("ascii", "ignore").split("\n"):
            if BACKPORT_STR in l: continue
            new_msg += l+"\n"
          if backport_pr_num: new_msg="%s%s%s\n" % (new_msg, BACKPORT_STR, backport_pr_num)
          already_seen.edit(body=new_msg)
    elif ("backport-ok" in old_labels):
      extra_labels["backport"][0]="backport-ok"

  # Add additional labels
  for lab in extra_testers: labels.append("allow-"+lab)
  for lab in extra_labels: labels.append(extra_labels[lab][0])
  if comp_warnings: labels.append("compilation-warnings")

  if cms_repo and issue.pull_request:
    if comparison_done:
      labels.append("comparison-available")
    elif comparison_notrun:
      labels.append("comparison-notrun")
    else:
      labels.append("comparison-pending")

  # Now updated the labels.
  missingApprovals = [x
                      for x in labels
                      if     not x.endswith("-approved")
                         and not x.startswith("orp")
                         and not x.startswith("tests")
                         and not x.startswith("pending-assignment")
                         and not x.startswith("comparison")
                         and not x.startswith("code-checks")
                         and not x.startswith("allow-")
                         and not x in ["backport", "urgent", "bug-fix", "new-feature", "backport-ok", "compilation-warnings"]]

  if not missingApprovals:
    print("The pull request is complete.")
  if missingApprovals:
    labels.append("pending-signatures")
  elif not "pending-assignment" in labels:
    labels.append("fully-signed")
  if need_external: labels.append("requires-external")
  labels = set(labels)
  print("New Labels:", sorted(labels))

  new_categories  = set ([])
  for nc_lab in pkg_categories:
    ncat = [ nc_lab for oc_lab in old_labels if oc_lab.startswith(nc_lab+'-') ]
    if ncat: continue
    new_categories.add(nc_lab)

  if new_assign_cats:
    new_l2s = ["@" + name
               for name, l2_categories in list(CMSSW_L2.items())
               for signature in new_assign_cats
               if signature in l2_categories]
    if not dryRun: issue.create_comment("New categories assigned: "+",".join(new_assign_cats)+"\n\n"+",".join(new_l2s)+" you have been requested to review this Pull request/Issue and eventually sign? Thanks")

  #update blocker massge
  if new_blocker:
    if not dryRun: issue.create_comment(HOLD_MSG+blockers+'\nThey need to issue an `unhold` command to remove the `hold` state or L1 can `unhold` it for all')
    print("Blockers:",blockers)

  print("Changed Labels:",labels-old_labels,old_labels-labels)
  if old_labels == labels:
    print("Labels unchanged.")
  elif not dryRunOrig:
    add_labels = True
    try: add_labels = repo_config.ADD_LABELS
    except: pass
    if add_labels: issue.edit(labels=list(labels))

  # Check if it needs to be automatically closed.
  if mustClose == True and issue.state == "open":
    print("This pull request must be closed.")
    if not dryRunOrig: issue.edit(state="closed")
 
  if not issue.pull_request:
    issueMessage = None
    if not already_seen:
      backport_msg=""
      if backport_pr_num: backport_msg="%s%s\n" % (BACKPORT_STR,backport_pr_num)
      uname = ""
      if issue.user.name: uname = issue.user.name.encode("ascii", "ignore")
      l2s = ", ".join([ "@" + name for name in CMSSW_ISSUES_TRACKERS ])
      issueMessage = format("%(msgPrefix)s @%(user)s"
                        " %(name)s.\n\n"
                        "%(l2s)s can you please review it and eventually sign/assign?"
                        " Thanks.\n\n"
                        "cms-bot commands are listed <a href=\"http://cms-sw.github.io/cms-bot-cmssw-issues.html\">here</a>\n%(backport_msg)s",
                        msgPrefix=NEW_ISSUE_PREFIX,
                        user=requestor,
                        name=uname,
                        backport_msg=backport_msg,
                        l2s=l2s)
    elif ("fully-signed" in labels) and (not "fully-signed" in old_labels):
      issueMessage = "This issue is fully signed and ready to be closed."
    print("Issue Message:",issueMessage)
    if issueMessage and not dryRun: issue.create_comment(issueMessage)
    return

  # get release managers
  SUPER_USERS = read_repo_file(repo_config, "super-users.yaml", [])
  releaseManagersList = ", ".join(["@" + x for x in set(releaseManagers + SUPER_USERS)])

  if cmssw_prs:
    global_test_params['PULL_REQUESTS'] = cmssw_prs
  if extra_wfs:
    global_test_params['MATRIX_EXTRAS'] = extra_wfs
  if release_queue:
    global_test_params['RELEASE_FORMAT'] = release_queue
  if not 'PULL_REQUESTS' in global_test_params:
    global_test_params['PULL_REQUESTS'] = '%s#%s' % (repository, prId)
  else:
    global_test_params['PULL_REQUESTS'] = '%s#%s %s' % (repository, prId, global_test_params['PULL_REQUESTS'])
  if ignore_tests:
    if ignore_tests == 'NONE': ignore_tests = ''
    global_test_params['IGNORE_BOT_TESTS'] = ignore_tests
  if enable_tests:
    if enable_tests == 'NONE': enable_tests = ''
    global_test_params['ENABLE_BOT_TESTS'] = enable_tests
  if release_arch:
    global_test_params['ARCHITECTURE_FILTER'] = release_arch
    
  print("All Parameters:",global_test_params)
  #For now, only trigger tests for cms-sw/cmssw and cms-sw/cmsdist
  if create_test_property:
    # trigger the tests and inform it in the thread.
    if trigger_test_on_signature and has_categories_approval: tests_requested = True
    if tests_requested:
      prs = global_test_params['PULL_REQUESTS'].strip().split(" ")
      for xpr in prs:
        repo_name,pr_num = xpr.split('#',1)
        pr_num = int(pr_num)
        rest_pr = [p for p in prs if p!=xpr]
        ex_msg = ''
        if rest_pr: ex_msg = "\nTested with other pull request(s) %s" % ','.join(rest_pr)
        if len(global_test_params)>1:
          ex_msg = ex_msg+"\nTest Parameters:"
          for p in global_test_params:
            if (p == 'PULL_REQUESTS') or (not global_test_params[p]): continue
            ex_msg = ex_msg+"\n  - **%s** = %s" % (p, global_test_params[p])
        if not repo_name in repo_cache: repo_cache[repo_name] = gh.get_repo(repo_name)
        pr_issue = issue
        if (repo_name!=repository) or (pr_num!=prId): pr_issue=repo_cache[repo_name].get_issue(pr_num)
        if not dryRun:
          pr_issue.create_comment( TRIGERING_TESTS_MSG+ex_msg)
        else:
          print('DryRun: Creating comment:%s\n\n%s' % (xpr, TRIGERING_TESTS_MSG+ex_msg))
      if not dryRun:
        create_properties_file_tests(repository, prId, global_test_params, dryRun, abort=False, repo_config=repo_config)

    elif abort_test:
      if not dryRun:
        issue.create_comment( TRIGERING_TESTS_ABORT_MSG )
        create_properties_file_tests(repository, prId, global_test_params, dryRun, abort=True)
      else:
        print('Dryrun: Aborting tests')

  # Do not complain about tests
  requiresTestMessage = " after it passes the integration tests"
  if "tests-approved" in labels:
    requiresTestMessage = " (tests are also fine)"
  elif "tests-rejected" in labels:
    requiresTestMessage = " (but tests are reportedly failing)"

  autoMergeMsg = ""
  if (("fully-signed" in labels) and ("tests-approved" in labels) and
      ((not "orp" in signatures) or (signatures["orp"] == "approved"))):
    autoMergeMsg = "This pull request will be automatically merged."
  else:
    if is_hold:
      autoMergeMsg = format("This PR is put on hold by %(blockers)s. They have"
                          " to `unhold` to remove the `hold` state or"
                          " %(managers)s will have to `merge` it by"
                          " hand.",
                          blockers=blockers,
                          managers=releaseManagersList)
    elif "new-package-pending" in labels:
      autoMergeMsg = format("This pull request requires a new package and "
                            " will not be merged. %(managers)s",
                            managers=releaseManagersList)
    elif ("orp" in signatures) and (signatures["orp"] != "approved"):
      autoMergeMsg = format("This pull request will now be reviewed by the release team"
                            " before it's merged. %(managers)s (and backports should be raised in the release meeting by the corresponding L2)",
                            managers=releaseManagersList)

  devReleaseRelVal = ""
  if (pr.base.ref in RELEASE_BRANCH_PRODUCTION) and (pr.base.ref != "master"):
    devReleaseRelVal = " and once validation in the development release cycle "+CMSSW_DEVEL_BRANCH+" is complete"

  if ("fully-signed" in labels) and (not "fully-signed" in old_labels):
    messageFullySigned = format("This pull request is fully signed and it will be"
                              " integrated in one of the next %(branch)s IBs"
                              "%(requiresTest)s"
                              "%(devReleaseRelVal)s."
                              " %(autoMerge)s",
                              requiresTest=requiresTestMessage,
                              autoMerge = autoMergeMsg,
                              devReleaseRelVal=devReleaseRelVal,
                              branch=pr.base.ref)
    print("Fully signed message updated")
    if not dryRun: issue.create_comment(messageFullySigned)

  unsigned = [k for (k, v) in list(signatures.items()) if v == "pending"]
  missing_notifications = ["@" + name
                            for name, l2_categories in list(CMSSW_L2.items())
                            for signature in signing_categories
                            if signature in l2_categories
                               and signature in unsigned and signature not in ["orp"] ]

  missing_notifications = set(missing_notifications)
  # Construct message for the watchers
  watchersMsg = ""
  if watchers:
    watchersMsg = format("%(watchers)s this is something you requested to"
                         " watch as well.\n",
                         watchers=", ".join(watchers))
  # Construct message for the release managers.
  managers = ", ".join(["@" + x for x in releaseManagers])

  releaseManagersMsg = ""
  if releaseManagers:
    releaseManagersMsg = format("%(managers)s you are the release manager for this.\n",
                                managers = managers)

  # Add a Warning if the pull request was done against a patch branch
  if cmssw_repo:
    warning_msg = ''
    if 'patchX' in pr.base.ref:
      print('Must warn that this is a patch branch')
      base_release = pr.base.ref.replace( '_patchX', '' )
      base_release_branch = re.sub( '[0-9]+$', 'X', base_release )
      warning_msg = format("Note that this branch is designed for requested bug "
                         "fixes specific to the %(base_rel)s release.\nIf you "
                         "wish to make a pull request for the %(base_branch)s "
                         "release cycle, please use the %(base_branch)s branch instead\n",
                         base_rel=base_release,
                         base_branch=base_release_branch)

    # We do not want to spam people for the old pull requests.
    messageNewPR = format("%(msgPrefix)s @%(user)s"
                        " %(name)s for %(branch)s.\n\n"
                        "It involves the following packages:\n\n"
                        "%(packages)s\n\n"
                        "%(new_package_message)s\n"
                        "%(l2s)s can you please review it and eventually sign?"
                        " Thanks.\n"
                        "%(watchers)s"
                        "%(releaseManagers)s"
                        "%(patch_branch_warning)s\n"
                        "cms-bot commands are listed <a href=\"http://cms-sw.github.io/cms-bot-cmssw-cmds.html\">here</a>\n",
                        msgPrefix=NEW_PR_PREFIX,
                        user=pr.user.login,
                        name=pr.user.name and "(%s)" % pr.user.name or "",
                        branch=pr.base.ref,
                        l2s=", ".join(missing_notifications),
                        packages="\n".join(packages),
                        new_package_message=new_package_message,
                        watchers=watchersMsg,
                        releaseManagers=releaseManagersMsg,
                        patch_branch_warning=warning_msg)

    messageUpdatedPR = format("Pull request #%(pr)s was updated."
                            " %(signers)s can you please check and sign again.\n",
                            pr=pr.number,
                            signers=", ".join(missing_notifications))
  else:
    messageNewPR = format("%(msgPrefix)s @%(user)s"
                          " %(name)s for branch %(branch)s.\n\n"
                          "%(l2s)s can you please review it and eventually sign?"
                          " Thanks.\n"
                          "%(watchers)s"
                          "cms-bot commands are listed <a href=\"http://cms-sw.github.io/cms-bot-cmssw-cmds.html\">here</a>\n",
                          msgPrefix=NEW_PR_PREFIX,
                          user=pr.user.login,
                          name=pr.user.name and "(%s)" % pr.user.name or "",
                          branch=pr.base.ref,
                          l2s=", ".join(missing_notifications),
                          watchers=watchersMsg)

    messageUpdatedPR = format("Pull request #%(pr)s was updated.",
                              pr=pr.number)

  # Finally decide whether or not we should close the pull request:
  messageBranchClosed = format("This branch is closed for updates."
                               " Closing this pull request.\n"
                               " Please bring this up in the ORP"
                               " meeting if really needed.\n")

  commentMsg = ""
  print("Status: Not see= %s, Updated: %s" % (already_seen, pull_request_updated))
  if (pr.base.ref in RELEASE_BRANCH_CLOSED) and (pr.state != "closed"):
    commentMsg = messageBranchClosed
  elif (not already_seen) or pull_request_updated:
    if not already_seen: commentMsg = messageNewPR
    else: commentMsg = messageUpdatedPR
    if (not triggerred_code_checks) and cmssw_repo and (pr.base.ref=="master") and ("code-checks" in signatures) and (signatures["code-checks"]=="pending"):
      trigger_code_checks=True
  elif new_categories:
    commentMsg = messageUpdatedPR
  elif not missingApprovals:
    print("Pull request is already fully signed. Not sending message.")
  else:
    print("Already notified L2 about " + str(pr.number))
  if commentMsg:
    print("The following comment will be made:")
    try:
      print(commentMsg.decode("ascii", "replace"))
    except:
      pass
  print("Code Checks:", trigger_code_checks, triggerred_code_checks)
  if trigger_code_checks and not triggerred_code_checks:
    if not dryRunOrig: issue.create_comment(TRIGERING_CODE_CHECK_MSG)
    else: print("Dryrun:",TRIGERING_CODE_CHECK_MSG)
    params = {"PULL_REQUEST" : "%s" % (prId)}
    create_properties_file_tests(repository, prId, params, dryRunOrig, abort=False, req_type="codechecks")

  if commentMsg and not dryRun:
    issue.create_comment(commentMsg)

  # Check if it needs to be automatically merged.
  if all(["fully-signed" in labels,
          "tests-approved" in labels,
          "orp-approved" in labels,
          not "hold" in labels,
          not "new-package-pending" in labels]):
    print("This pull request can be automatically merged")
    mustMerge = True
  else:
    print("This pull request will not be automatically merged.")
  if mustMerge == True:
    print("This pull request must be merged.")
    if not dryRun and (pr.state == "open"): pr.merge()

