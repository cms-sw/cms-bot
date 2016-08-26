from categories import CMSSW_CATEGORIES, CMSSW_L2, CMSSW_L1, TRIGGER_PR_TESTS, CMSSW_ISSUES_TRACKERS
from releases import RELEASE_BRANCH_MILESTONE, RELEASE_BRANCH_PRODUCTION, RELEASE_BRANCH_CLOSED
from releases import RELEASE_MANAGERS, SPECIAL_RELEASE_MANAGERS
from releases import DEVEL_RELEASE_CYCLE
from cms_static import VALID_CMSDIST_BRANCHES, NEW_ISSUE_PREFIX, NEW_PR_PREFIX, ISSUE_SEEN_MSG, BUILD_REL, GH_CMSSW_REPO, GH_CMSDIST_REPO, CMSDIST_REPO_NAME, CMSSW_REPO_NAME, CMSBOT_IGNORE_MSG, GITHUB_IGNORE_ISSUES
from cms_static import CMSSW_PULL_REQUEST_COMMANDS, CMSSW_ISSUE_COMMANDS
import yaml
import re, time
from sys import exit, argv
from os.path import abspath, dirname, join
from github import UnknownObjectException
from socket import setdefaulttimeout
setdefaulttimeout(120)
try:
  SCRIPT_DIR = dirname(abspath(__file__))
except Exception, e :
  SCRIPT_DIR = dirname(abspath(argv[0]))

TRIGERING_TESTS_MSG = 'The tests are being triggered in jenkins.'
IGNORING_TESTS_MSG = 'Ignoring test request.'
TESTS_RESULTS_MSG = '^\s*[-|+]1\s*$'
FAILED_TESTS_MSG = 'The jenkins tests job failed, please try again.'
HOLD_MSG = "Pull request has been put on hold by "
#Regexp to match the test requests
REGEX_TEST_REQ = re.compile("^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)test(\s+with\s+"+CMSDIST_REPO_NAME+"#([0-9]+)|)\s*$", re.I)
#Change the CMSDIST_PR_INDEX if you update the TEST_REQ regexp
CMSDIST_PR_INDEX = 5
TEST_WAIT_GAP=720

# Prepare various comments regardless of whether they will be made or not.
def format(s, **kwds):
  return s % kwds

#
# creates a properties file to trigger the test of the pull request
#
def create_properties_file_tests(repository, pr_number, cmsdist_pr, dryRun ):
  out_file_name = 'trigger-tests-%s-%s.properties' % (repository.split("/")[1], pr_number)
  if dryRun:
    print 'Not creating cleanup properties file (dry-run): %s' % out_file_name
  else:
    print 'Creating properties file %s' % out_file_name
    out_file = open( out_file_name , 'w' )
    if repository.endswith("/"+GH_CMSDIST_REPO):
      out_file.write( '%s=%s\n' % ( 'CMSDIST_PR', pr_number ) )
    else:
      out_file.write( '%s=%s\n' % ( 'PULL_REQUEST_LIST', pr_number ) )
      out_file.write( '%s=%s\n' % ( 'CMSDIST_PR', cmsdist_pr ) )
    out_file.close()

# Update the milestone for a given issue.
def updateMilestone(repo, issue, pr, dryRun):
  if issue.milestone:
    return
  branch = pr.base.label.split(":")[1]
  milestoneId = RELEASE_BRANCH_MILESTONE.get(branch, None)
  if not milestoneId:
    print "Unable to find a milestone for the given branch"
    return
  milestone = repo.get_milestone(milestoneId)
  if issue.milestone:
    if issue.milestone == milestone:
      return
    else:
      print "Changing milestone from ",issue.milestone," to ",milestone
  print "Setting milestone to %s" % milestone.title
  if dryRun:
    return
  issue.edit(milestone=milestone)

def find_last_comment(issue, user, match):
  last_comment = None
  for comment in issue.get_comments():
    if user != comment.user.login:
      continue
    if not re.match(match,comment.body.encode("ascii", "ignore").strip("\n\t\r "),re.MULTILINE):
      continue
    last_comment = comment
    print "Matched comment from ",comment.user.login+" with comment id ",comment.id
  return last_comment

def modify_comment(comment, match, replace, dryRun):
  comment_msg = comment.body.encode("ascii", "ignore")
  if match:
    new_comment_msg = re.sub(match,replace,comment_msg)
  else:
    new_comment_msg = comment_msg+"\n"+replace
  if new_comment_msg != comment_msg:
    if not dryRun:
      comment.edit(new_comment_msg)
      print "Message updated"
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

def ignore_issue(repo, issue):
  if (repo.full_name in GITHUB_IGNORE_ISSUES) and (issue.number in GITHUB_IGNORE_ISSUES[repo.full_name]):
    return True
  if re.match(BUILD_REL, issue.title):
    return True
  if re.match(CMSBOT_IGNORE_MSG, issue.body.encode("ascii", "ignore").split("\n",1)[0].strip() ,re.I):
    return True
  return False

def check_extra_labels(first_line, extra_labels):
  if "bug" in first_line:
    extra_labels["type"]="bug-fix"
  elif "feature" in first_line:
    extra_labels["type"]="new-feature"
  elif "urgent" in first_line:
    extra_labels["urgent"]="urgent"
  elif "backport" in first_line:
    extra_labels["backport"]="backport"

def process_pr(gh, repo, issue, dryRun, cmsbuild_user="cmsbuild"):
  if ignore_issue(repo, issue): return
  prId = issue.number
  repository = repo.full_name
  print "Working on ",repo.full_name," for PR/Issue ",prId
  cmssw_repo = False
  create_test_property = False
  if repository.endswith("/"+GH_CMSSW_REPO): cmssw_repo = True
  packages = set([])
  create_external_issue = False
  add_external_category = False
  signing_categories = set([])
  new_package_message = ""
  mustClose = False
  releaseManagers = []
  signatures = {}
  watchers = []
  #Process Pull Request
  pkg_categories = set([])
  if issue.pull_request:
    try:
      pr   = repo.get_pull(prId)
    except:
      print "Could not find the pull request ",prId,", may be it is an issue"
      return
    # A pull request is by default closed if the branch is a closed one.
    if pr.base.ref in RELEASE_BRANCH_CLOSED: mustClose = True
    # Process the changes for the given pull request so that we can determine the
    # signatures it requires.
    if cmssw_repo:
      packages = sorted([x for x in set(["/".join(x.filename.split("/", 2)[0:2])
                           for x in pr.get_files()])])
      updateMilestone(repo, issue, pr, dryRun)
      create_test_property = True
    else:
      add_external_category = True
      packages = set (["externals/"+repository])
      if repository != CMSDIST_REPO_NAME:
        if not repository.endswith("/cms-bot"): create_external_issue = True
      else:
        create_test_property = True
        if not re.match(VALID_CMSDIST_BRANCHES,pr.base.ref):
          print "Skipping PR as it does not belong to valid CMSDIST branch"
          return

    print "Following packages affected:"
    print "\n".join(packages)
    pkg_categories = set([category for package in packages
                              for category, category_packages in CMSSW_CATEGORIES.items()
                              if package in category_packages])
    signing_categories.update(pkg_categories)

    # For PR, we always require tests.
    signing_categories.add("tests")
    if add_external_category: signing_categories.add("externals")
    # We require ORP approval for releases which are in production.
    # or all externals package
    if (not cmssw_repo) or (pr.base.ref in RELEASE_BRANCH_PRODUCTION):
      print "This pull request requires ORP approval"
      signing_categories.add("orp")
      for l1 in CMSSW_L1:
        if not l1 in CMSSW_L2: CMSSW_L2[l1]=[]
        if not "orp" in CMSSW_L2[l1]: CMSSW_L2[l1].append("orp")

    print "Following categories affected:"
    print "\n".join(signing_categories)

    if cmssw_repo:
      # If there is a new package, add also a dummy "new" category.
      all_packages = [package for category_packages in CMSSW_CATEGORIES.values()
                              for package in category_packages]
      has_category = all([package in all_packages for package in packages])
      if not has_category:
        new_package_message = "\nThe following packages do not have a category, yet:\n\n"
        new_package_message += "\n".join([package for package in packages if not package in all_packages]) + "\n"
        print new_package_message
        signing_categories.add("new-package")

    # Add watchers.yaml information to the WATCHERS dict.
    WATCHERS = (yaml.load(file(join(SCRIPT_DIR, "watchers.yaml"))))
    # Given the packages check if there are additional developers watching one or more.
    author = pr.user.login
    watchers = set([user for package in packages
                         for user, watched_regexp in WATCHERS.items()
                         for regexp in watched_regexp
                         if re.match("^" + regexp + ".*", package) and user != author])
    #Handle category watchers
    for user, cats in (yaml.load(file(join(SCRIPT_DIR, "category-watchers.yaml")))).items():
      for cat in cats:
        if cat in signing_categories:
          print "Added ",user, " to watch due to cat",cat
          watchers.add(user)

    # Handle watchers
    watchingGroups = yaml.load(file(join(SCRIPT_DIR, "groups.yaml")))
    for watcher in [x for x in watchers]:
      if not watcher in watchingGroups: continue
      watchers.remove(watcher)
      watchers.update(set(watchingGroups[watcher]))      
    watchers = set(["@" + u for u in watchers])
    print "Watchers " + ", ".join(watchers)

    last_commit = None
    try:
      # This requires at least PyGithub 1.23.0. Making it optional for the moment.
      last_commit = pr.get_commits().reversed[0].commit
    except:
      # This seems to fail for more than 250 commits. Not sure if the
      # problem is github itself or the bindings.
      last_commit = pr.get_commits()[pr.commits - 1].commit
    last_commit_date = last_commit.committer.date
    print "Latest commit by ",last_commit.committer.name.encode("ascii", "ignore")," at ",last_commit_date
    print "Latest commit message: ",last_commit.message.encode("ascii", "ignore")
    print "Latest commit sha: ",last_commit.sha
    releaseManagers=list(set(RELEASE_MANAGERS.get(pr.base.ref, [])+SPECIAL_RELEASE_MANAGERS))

  # Process the issue comments
  signatures = dict([(x, "pending") for x in signing_categories])
  already_seen = False
  pull_request_updated = False
  comparison_done = False
  comparison_notrun = False
  tests_already_queued = False
  tests_requested = False
  mustMerge = False
  external_issue_number=""
  trigger_test_on_signature = True
  has_categories_approval = False
  cmsdist_pr = ''
  assign_cats = {}
  hold = {}
  extra_labels = {}
  last_test_start_time = None
  body_firstline = issue.body.encode("ascii", "ignore").split("\n",1)[0].strip()
  if (issue.user.login == cmsbuild_user) and \
     re.match(ISSUE_SEEN_MSG,body_firstline):
    already_seen = True
  elif re.match("^type\s+(bug(-fix|fix|)|(new-|)feature)|urgent|backport\s+(of\s+|)#\d+$", body_firstline, re.I):
    check_extra_labels(body_firstline.lower(), extra_labels)
  for comment in issue.get_comments():
    commenter = comment.user.login
    comment_msg = comment.body.encode("ascii", "ignore")

    # The first line is an invariant.
    comment_lines = [ l.strip() for l in comment_msg.split("\n") if l.strip() ]
    first_line = comment_lines[0:1]
    if not first_line: continue
    first_line = first_line[0]
    if (commenter == cmsbuild_user) and re.match(ISSUE_SEEN_MSG, first_line):
      already_seen = True
      pull_request_updated = False
      if create_external_issue:
        external_issue_number=comment_msg.split("external issue "+CMSDIST_REPO_NAME+"#",2)[-1].split("\n")[0]
        if not re.match("^[1-9][0-9]*$",external_issue_number):
          print "ERROR: Unknow external issue PR format:",external_issue_number
          external_issue_number=""
      continue

    assign_type, new_cats = get_assign_categories(first_line)
    if new_cats:
      if (assign_type == "new categories assigned:") and (commenter == cmsbuild_user):
        for ex_cat in new_cats:
          if ex_cat in assign_cats: assign_cats[ex_cat] = 1
      if ((commenter in CMSSW_L2) and [x for x in CMSSW_L2[commenter] if x in signing_categories]) or \
          (not issue.pull_request and (commenter in  CMSSW_ISSUES_TRACKERS + CMSSW_L1)):
        if assign_type == "assign":
          for ex_cat in new_cats:
            if not ex_cat in signing_categories:
              assign_cats[ex_cat] = 0
              signing_categories.add(ex_cat)
        elif assign_type == "unassign":
          for ex_cat in new_cats:
            if ex_cat in assign_cats:
              assign_cats.pop(ex_cat)
              signing_categories.remove(ex_cat)
      continue

    # Some of the special users can say "hold" prevent automatic merging of
    # fully signed PRs.
    if re.match("^hold$", first_line, re.I):
      if commenter in CMSSW_L1 + CMSSW_L2.keys() + releaseManagers: hold[commenter]=1
      continue
    if re.match("^type\s+(bug(-fix|fix|)|(new-|)feature)|urgent|backport\s+(of\s+|)#\d+$", first_line, re.I):
      if commenter in CMSSW_L1 + CMSSW_L2.keys() + releaseManagers + [issue.user.login]:
        check_extra_labels(first_line.lower(), extra_labels)
      continue
    if re.match("^unhold$", first_line, re.I):
      if commenter in CMSSW_L1:
        hold = {}
      elif commenter in CMSSW_L2.keys() + releaseManagers:
        if hold.has_key(commenter): del hold[commenter]
        for u in hold: hold[u]=1
      continue
    if (commenter == cmsbuild_user) and (re.match("^"+HOLD_MSG+".+", first_line)):
      for u in first_line.split(HOLD_MSG,2)[1].split(","):
        u = u.strip().lstrip("@")
        if hold.has_key(u): hold[u]=0
    if re.match("^close$", first_line, re.I):
      if (not issue.pull_request and (commenter in  CMSSW_ISSUES_TRACKERS + CMSSW_L1)):
        mustClose = True
      continue

    # Ignore all other messages which are before last commit.
    if issue.pull_request and (comment.created_at < last_commit_date):
      print "Ignoring comment done before the last commit."
      pull_request_updated = True
      continue

    # Check for cmsbuild_user comments and tests requests only for pull requests
    if commenter == cmsbuild_user:
      if not issue.pull_request: continue
      if re.match("Comparison is ready", first_line):
        if ('tests' in signatures) and signatures["tests"]!='pending': comparison_done = True
      elif re.match("^Comparison not run.+",first_line):
        if ('tests' in signatures) and signatures["tests"]!='pending': comparison_notrun = True
      elif re.match( FAILED_TESTS_MSG, first_line) or re.match(IGNORING_TESTS_MSG, first_line):
        tests_already_queued = False
        tests_requested = False
        signatures["tests"] = "pending"
        trigger_test_on_signature = False
      elif re.match("Pull request ([^ #]+|)[#][0-9]+ was updated[.].*", first_line):
        pull_request_updated = False
      elif re.match( TRIGERING_TESTS_MSG, first_line):
        tests_already_queued = True
        tests_requested = False
        signatures["tests"] = "started"
        trigger_test_on_signature = False
        last_test_start_time = comment.created_at
      elif re.match( TESTS_RESULTS_MSG, first_line):
        test_sha = comment_lines[1:2]
        if test_sha: test_sha = test_sha[0].replace("Tested at: ","").strip()
        if (test_sha != last_commit.sha) and (test_sha != 'UNKNOWN'):
          print "Ignoring test results for sha:",test_sha
          continue
        trigger_test_on_signature = False
        tests_already_queued = False
        tests_requested = False
        comparison_done = False
        comparison_notrun = False
        if re.match('^\s*[+]1\s*$', first_line):
          signatures["tests"] = "approved"
        else:
          signatures["tests"] = "rejected"
        print 'Previous tests already finished, resetting test request state to ',signatures["tests"]
      continue

    if issue.pull_request:
      # Check if the release manager asked for merging this.
      if (commenter in releaseManagers + CMSSW_L1) and re.match("^\s*(merge)\s*$", first_line, re.I):
        mustMerge = True
        mustClose = False
        continue

      # Check if the someone asked to trigger the tests
      if commenter in TRIGGER_PR_TESTS + CMSSW_L2.keys() + CMSSW_L1 + releaseManagers:
        m = REGEX_TEST_REQ.match(first_line)
        if m:
          print 'Tests requested:', commenter, 'asked to test this PR'
          trigger_test_on_signature = False
          cmsdist_pr = ''
          if tests_already_queued:
            print "Test results not obtained in ",comment.created_at-last_test_start_time
            diff = time.mktime(comment.created_at.timetuple()) - time.mktime(last_test_start_time.timetuple())
            if diff>=TEST_WAIT_GAP:
              print "Looks like tests are stuck, will try to re-queue"
              tests_already_queued = False
          if not tests_already_queued:
            print 'cms-bot will request test for this PR'
            tests_requested = True
            comparison_done = False
            comparison_notrun = False
            if cmssw_repo:
              cmsdist_pr = m.group(CMSDIST_PR_INDEX)
              if not cmsdist_pr: cmsdist_pr = ''
            signatures["tests"] = "pending"
          else:
            print 'Tests already request for this PR'
          continue

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
          if sign == "orp": mustClose = True
      elif ctype == "reopen":
        if "orp" in CMSSW_L2[commenter]:
          signatures["orp"] = "pending"
          mustClose = False
      continue

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

  print "All assigned cats:",",".join(assign_cats.keys())
  print "Newly assigned cats:",",".join(new_assign_cats)

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

  # Add additional labels
  for lab in extra_labels: labels.append(extra_labels[lab])

  if cmssw_repo and issue.pull_request:
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
                         and not x in ["backport", "urgent", "bug-fix", "new-feature"]]

  if not missingApprovals:
    print "The pull request is complete."
  if missingApprovals:
    labels.append("pending-signatures")
  elif not "pending-assignment" in labels:
    labels.append("fully-signed")
  labels = set(labels)

  print "The labels of the pull request should be:\n  "+"\n  ".join(labels)

  # We update labels only if they are different.
  old_labels = set([x.name for x in issue.labels])
  new_categories  = set ([])
  for nc_lab in pkg_categories:
    ncat = [ nc_lab for oc_lab in old_labels if oc_lab.startswith(nc_lab+'-') ]
    if ncat: continue
    new_categories.add(nc_lab)

  if new_assign_cats:
    new_l2s = ["@" + name
               for name, l2_categories in CMSSW_L2.items()
               for signature in new_assign_cats
               if signature in l2_categories]
    if not dryRun: issue.create_comment("New categories assigned: "+",".join(new_assign_cats)+"\n\n"+",".join(new_l2s)+" you have been requested to review this Pull request/Issue and eventually sign? Thanks")

  #update blocker massge
  if new_blocker:
    if not dryRun: issue.create_comment(HOLD_MSG+blockers+'\nThey need to issue an `unhold` command to remove the `hold` state or L1 can `unhold` it for all')
    print "Blockers:",blockers

  labels_changed = True
  if old_labels == labels:
    labels_changed = False
    print "Labels unchanged."
  elif not dryRun:
    issue.edit(labels=list(labels))

  # Check if it needs to be automatically closed.
  if mustClose == True and issue.state == "open":
    print "This pull request must be closed."
    if not dryRun: issue.edit(state="closed")
 
  if not issue.pull_request:
    issueMessage = None
    if not already_seen:
      uname = ""
      if issue.user.name: uname = issue.user.name.encode("ascii", "ignore")
      l2s = ", ".join([ "@" + name for name in CMSSW_ISSUES_TRACKERS ])
      issueMessage = format("%(msgPrefix)s @%(user)s"
                        " %(name)s.\n\n"
                        "%(l2s)s can you please review it and eventually sign/assign?"
                        " Thanks.\n\n"
                        "cms-bot commands are list here %(issue_url)s\n",
                        msgPrefix=NEW_ISSUE_PREFIX,
                        user=issue.user.login.encode("ascii", "ignore"),
                        name=uname,
                        l2s=l2s,
                        issue_url=CMSSW_ISSUE_COMMANDS)
    elif ("fully-signed" in labels) and (not "fully-signed" in old_labels):
      issueMessage = "This issue is fully signed and ready to be closed."
    print "Issue Message:",issueMessage
    if issueMessage and not dryRun: issue.create_comment(issueMessage)
    return

  # get release managers
  SUPER_USERS = (yaml.load(file(join(SCRIPT_DIR, "super-users.yaml"))))
  releaseManagersList = ", ".join(["@" + x for x in set(releaseManagers + SUPER_USERS)])

  #For now, only trigger tests for cms-sw/cmssw and cms-sw/cmsdist
  if create_test_property:
    # trigger the tests and inform it in the thread.
    if trigger_test_on_signature and has_categories_approval:
      tests_requested = True
    if tests_requested:
      test_msg = TRIGERING_TESTS_MSG
      cmsdist_issue = None
      if cmsdist_pr:
        try:
          cmsdist_repo = gh.get_repo(CMSDIST_REPO_NAME)
          cmsdist_pull = cmsdist_repo.get_pull(int(cmsdist_pr))
          cmsdist_issue = cmsdist_repo.get_issue(int(cmsdist_pr))
          test_msg = test_msg+"\nUsing externals from "+CMSDIST_REPO_NAME+"#"+cmsdist_pr
        except UnknownObjectException as e:
          print "Error getting cmsdist PR:",e.data['message']
          test_msg = IGNORING_TESTS_MSG+"\n**ERROR**: Unable to find cmsdist Pull request "+CMSDIST_REPO_NAME+"#"+cmsdist_pr
      if not dryRun:
        issue.create_comment( test_msg )
        if cmsdist_issue: cmsdist_issue.create_comment(TRIGERING_TESTS_MSG+"\nUsing cmssw from "+CMSSW_REPO_NAME+"#"+str(prId))
        if (not cmsdist_pr) or cmsdist_issue:
          create_properties_file_tests( repository, prId, cmsdist_pr, dryRun)

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
      autoMergeMsg = format("This pull request requires discussion in the"
                            " ORP meeting before it's merged. %(managers)s",
                            managers=releaseManagersList)

  devReleaseRelVal = ""
  if pr.base.ref in DEVEL_RELEASE_CYCLE:
    devReleaseRelVal = " and once validation in the development release cycle "+DEVEL_RELEASE_CYCLE[pr.base.ref]+" is complete"

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
    print "Fully signed message updated"
    if not dryRun: issue.create_comment(messageFullySigned)

  unsigned = [k for (k, v) in signatures.items() if v == "pending"]
  missing_notifications = ["@" + name
                            for name, l2_categories in CMSSW_L2.items()
                            for signature in signing_categories
                            if signature in l2_categories
                               and signature in unsigned]

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
      print 'Must warn that this is a patch branch'
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
                        "cms-bot commands are list here %(issue_url)s\n",
                        msgPrefix=NEW_PR_PREFIX,
                        user=pr.user.login,
                        name=pr.user.name and "(%s)" % pr.user.name or "",
                        branch=pr.base.ref,
                        l2s=", ".join(missing_notifications),
                        packages="\n".join(packages),
                        new_package_message=new_package_message,
                        watchers=watchersMsg,
                        releaseManagers=releaseManagersMsg,
                        patch_branch_warning=warning_msg,
                        issue_url=CMSSW_PULL_REQUEST_COMMANDS)

    messageUpdatedPR = format("Pull request #%(pr)s was updated."
                            " %(signers)s can you please check and sign again.",
                            pr=pr.number,
                            signers=", ".join(missing_notifications))
  else:
    if create_external_issue:
      if not already_seen:
        if dryRun:
          print "Should create a new issue in ",CMSDIST_REPO_NAME," for this PR"
        else:
          external_managers = ["@" + name for name, l2_categories in CMSSW_L2.items() if "externals" in l2_categories]
          cmsdist_repo  = gh.get_repo(CMSDIST_REPO_NAME)
          cmsdist_title = format("%(repo)s#%(pr)s: %(title)s",
                                 title=pr.title.encode("ascii", "ignore"),
                                 repo=repository,
                                 pr=pr.number)
          cmsdist_body = format("%(msgPrefix)s @%(user)s"
                                " %(name)s for branch %(branch)s.\n\n"
                                "Pull Request Reference: %(repo)s#%(pr)s\n\n"
                                "%(externals_l2s)s can you please review it and eventually sign? Thanks.\n",
                                msgPrefix=NEW_PR_PREFIX,
                                repo=repository,
                                user=pr.user.login,
                                name=pr.user.name and "(%s)" % pr.user.name or "",
                                branch=pr.base.ref,
                                externals_l2s=", ".join(external_managers),
                                pr=pr.number)
          cissue = cmsdist_repo.create_issue(cmsdist_title, cmsdist_body)
          external_issue_number = str(cissue.number)
          print "Created a new issue ",CMSDIST_REPO_NAME,"#",external_issue_number
      if pull_request_updated and external_issue_number:
        if dryRun:
          print "Should add an update message for issue ",CMSDIST_REPO_NAME,"#",external_issue_number
        else:
          cmsdist_repo  = gh.get_repo(CMSDIST_REPO_NAME)
          cissue = cmsdist_repo.get_issue(int(external_issue_number))
          cmsdist_body = format("Pull request %(repo)s#%(pr)s was updated.\n"
                                "Latest update by %(name)s with commit message\n%(message)s",
                                repo=repository,
                                pr=pr.number,
                                name=last_commit.committer.name.encode("ascii", "ignore"),
                                message=last_commit.message.encode("ascii", "ignore"))
          cissue.create_comment(cmsdist_body)
    cmsdist_issue = ""
    if external_issue_number:
      cmsdist_issue="\n\nexternal issue "+CMSDIST_REPO_NAME+"#"+external_issue_number

    messageNewPR = format("%(msgPrefix)s @%(user)s"
                          " %(name)s for branch %(branch)s.\n\n"
                          "%(l2s)s can you please review it and eventually sign?"
                          " Thanks.\n"
                          "%(watchers)s"
                          "You can sign-off by replying to this message having"
                          " '+1' in the first line of your reply.\n"
                          "You can reject by replying  to this message having"
                          " '-1' in the first line of your reply."
                          "%(cmsdist_issue)s",
                          msgPrefix=NEW_PR_PREFIX,
                          user=pr.user.login,
                          name=pr.user.name and "(%s)" % pr.user.name or "",
                          branch=pr.base.ref,
                          title=pr.title.encode("ascii", "ignore"),
                          l2s=", ".join(missing_notifications),
                          watchers=watchersMsg,
                          cmsdist_issue=cmsdist_issue)

    messageUpdatedPR = format("Pull request #%(pr)s was updated."
                              "%(cmsdist_issue)s",
                              pr=pr.number,
                              cmsdist_issue=cmsdist_issue)

  # Finally decide whether or not we should close the pull request:
  messageBranchClosed = format("This branch is closed for updates."
                               " Closing this pull request.\n"
                               " Please bring this up in the ORP"
                               " meeting if really needed.\n")

  commentMsg = ""
  if (pr.base.ref in RELEASE_BRANCH_CLOSED) and (pr.state != "closed"):
    commentMsg = messageBranchClosed
  elif not already_seen:
    commentMsg = messageNewPR
  elif pull_request_updated or new_categories:
    commentMsg = messageUpdatedPR
  elif not missingApprovals:
    print "Pull request is already fully signed. Not sending message."
  else:
    print "Already notified L2 about " + str(pr.number)
  if commentMsg:
    print "The following comment will be made:"
    try:
      print commentMsg.decode("ascii", "replace")
    except:
      pass

  if commentMsg and not dryRun:
    issue.create_comment(commentMsg)

  # Check if it needs to be automatically merged.
  if all(["fully-signed" in labels,
          "tests-approved" in labels,
          "orp-approved" in labels,
          not "hold" in labels,
          not "new-package-pending" in labels]):
    print "This pull request can be automatically merged"
    mustMerge = True
  else:
    print "This pull request will not be automatically merged."

  if mustMerge == True:
    print "This pull request must be merged."
    if not dryRun:
        try:
          pr.merge()
        except:
          pass

