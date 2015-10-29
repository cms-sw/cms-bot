from categories import CMSSW_CATEGORIES, CMSSW_L2, CMSSW_L1, TRIGGER_PR_TESTS
from releases import RELEASE_BRANCH_MILESTONE, RELEASE_BRANCH_PRODUCTION, RELEASE_BRANCH_CLOSED
from releases import RELEASE_MANAGERS
from releases import DEVEL_RELEASE_CYCLE
import yaml
import re
from sys import exit

TRIGERING_TESTS_MSG = 'The tests are being triggered in jenkins.'
TESTS_RESULTS_MSG = '^\s*[-|+]1\s*$'
FAILED_TESTS_MSG = 'The jenkins tests job failed, please try again.'

# Prepare various comments regardless of whether they will be made or not.
def format(s, **kwds):
  return s % kwds

#
# creates a properties file to trigger the test of the pull request
#
def create_properties_file_tests( pr_number, dryRun ):
  out_file_name = 'trigger-tests-%s.properties' % pr_number
  if dryRun:
    print 'Not creating cleanup properties file (dry-run): %s' % out_file_name
  else:
    print 'Creating properties file %s' % out_file_name
    out_file = open( out_file_name , 'w' )
    out_file.write( '%s=%s\n' % ( 'PULL_REQUEST_LIST', pr_number ) )
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

def process_pr(gh, repo, prId, repository, dryRun):
  print "Working on ",repo.full_name," for PR ",prId
  external_issue_repo_name = "cms-sw/cmsdist"
  cmssw_repo = False
  if repository == "cms-sw/cmssw": cmssw_repo = True
  try:
    pr   = repo.get_pull(prId)
  except:
    print "Could not find the pull request ",prId,", may be it is an issue"
    return
  # Process the changes for the given pull request so that we can determine the
  # signatures it requires.
  create_external_issue = False
  add_external_category = False
  if cmssw_repo:
    packages = sorted([x for x in set(["/".join(x.filename.split("/", 2)[0:2])
                         for x in pr.get_files()])])

  else:
    add_external_category = True
    packages = set (["externals/"+repository])
    if repository != external_issue_repo_name: create_external_issue = True

  print "Following packages affected:"
  print "\n".join(packages)
  signing_categories = set([category for package in packages
                            for category, category_packages in CMSSW_CATEGORIES.items()
                            if package in category_packages])

  # We always require tests.
  signing_categories.add("tests")
  if add_external_category:
    signing_categories.add("externals")
  # We require ORP approval for releases which are in production.
  # or all externals package
  if (not cmssw_repo) or (pr.base.ref in RELEASE_BRANCH_PRODUCTION):
    print "This pull request requires ORP approval"
    signing_categories.add("orp")

  print "Following categories affected:"
  print "\n".join(signing_categories)

  if cmssw_repo:
    # If there is a new package, add also a dummy "new" category.
    all_packages = [package for category_packages in CMSSW_CATEGORIES.values()
                            for package in category_packages]
    has_category = all([package in all_packages for package in packages])
    new_package_message = ""
    if not has_category:
      new_package_message = "\nThe following packages do not have a category, yet:\n\n"
      new_package_message += "\n".join([package for package in packages if not package in all_packages]) + "\n"
      signing_categories.add("new-package")

  # Add watchers.yaml information to the WATCHERS dict.
  WATCHERS = (yaml.load(file("watchers.yaml")))
  # Given the packages check if there are additional developers watching one or more.
  author = pr.user.login
  watchers = set([user for package in packages
                       for user, watched_regexp in WATCHERS.items()
                       for regexp in watched_regexp
                       if re.match("^" + regexp + ".*", package) and user != author])
  # Handle watchers
  watchingGroups = yaml.load(file("groups.yaml"))
  for watcher in [x for x in watchers]:
    if not watcher in watchingGroups:
      continue
    watchers.remove(watcher)
    watchers.update(set(watchingGroups[watcher]))
  watchers = set(["@" + u for u in watchers])
  print "Watchers " + ", ".join(watchers)

  issue = repo.get_issue(prId)
  updateMilestone(repo, issue, pr, dryRun)

  # Process the issue comments
  signatures = dict([(x, "pending") for x in signing_categories])
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
  is_hold = False
  already_seen = False
  pull_request_updated = False
  comparison_done = False
  tests_already_queued = False
  tests_requested = False
  # A pull request is by default closed if the branch is a closed one.
  mustClose = False
  mustMerge = False
  if pr.base.ref in RELEASE_BRANCH_CLOSED:
    mustClose = True
  requiresL1 = False
  releaseManagers=RELEASE_MANAGERS.get(pr.base.ref, [])
  external_issue_number=""
  trigger_test_on_signature = True
  has_categories_approval = False
  for comment in issue.get_comments():
    comment_date = comment.created_at
    commenter = comment.user.login
    # Check special cmsbuild messages:
    # - Check we did not announce the pull request already
    # - Check we did not announce changes already
    comment_msg = comment.body.encode("ascii", "ignore")
    if commenter == "cmsbuild":
      if re.match("A new Pull Request was created by", comment_msg):
        already_seen = True
        pull_request_updated = False
        if create_external_issue:
          external_issue_number=comment_msg.split("external issue "+external_issue_repo_name+"#",2)[-1].split("\n")[0]
          if not re.match("^[1-9][0-9]*$",external_issue_number):
            print "ERROR: Unknow external issue PR format:",external_issue_number
            external_issue_number=""

    # Ignore all other messages which are before last commit.
    if comment_date < last_commit_date:
      print "Ignoring comment done before the last commit."
      pull_request_updated = True
      continue

    # The first line is an invariant.
    first_line = ""
    for l in comment_msg.split("\n"):
      if re.match("^[\n\t\r ]*$",l): continue
      first_line = l.strip("\n\t\r ")
      break

    # Check for cmsbuild comments
    if commenter == "cmsbuild":
      if re.match("Comparison is ready", first_line):
        comparison_done = True
        trigger_test_on_signature = False
      elif re.match( FAILED_TESTS_MSG, first_line):
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
      elif re.match( TESTS_RESULTS_MSG, first_line):
        trigger_test_on_signature = False
        tests_already_queued = False
        tests_requested = False
        if re.match('^\s*[+]1\s*$', first_line):
          signatures["tests"] = "approved"
        else:
          signatures["tests"] = "rejected"
        print 'Previous tests already finished, resetting test request state to ',signatures["tests"]
      continue

    # Check if the someone asked to trigger the tests
    if (commenter in TRIGGER_PR_TESTS
        or commenter in releaseManagers
        or commenter in CMSSW_L2.keys()):
      if re.match("^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)test\s*$", first_line, re.I):
        print 'Tests requested:', commenter, 'asked to test this PR'
        trigger_test_on_signature = False
        if not tests_already_queued:
          print 'cms-bot will request test for this PR'
          tests_requested = True
          comparison_done = False
          signatures["tests"] = "pending"
        else:
          print 'Tests already request for this PR'
        continue

    # Check actions made by L1.
    # L1 signatures are only relevant for closed releases where
    # we have a orp signature requested.
    # Approving a pull request, sign it.
    # Rejecting a pull request, will also close it.
    # Use "reopen" to open a closed pull request.
    if commenter in CMSSW_L1:
      requiresL1 = True
      if not "orp" in signing_categories:
        requiresL1 = False
      elif re.match("^([+]1|approve[d]?)$", first_line, re.I):
        signatures["orp"] = "approved"
        mustClose = False
      elif re.match("^([-]1|reject|rejected)$", first_line, re.I):
        signatures["orp"] = "rejected"
        mustClose = True
      elif re.match("reopen", first_line, re.I):
        signatures["orp"] = "pending"
        mustClose = False

    # Check if the release manager asked for merging this.
    if commenter in releaseManagers:
      if re.match("merge", first_line, re.I):
        mustMerge = True

    # Check L2 signoff for users in this PR signing categories
    if commenter in CMSSW_L2 and [x for x in CMSSW_L2[commenter] if x in signing_categories]:
      if re.match("^([+]1|approve[d]?|sign|signed)$", first_line, re.I):
        for sign in CMSSW_L2[commenter]:
          signatures[sign] = "approved"
          has_categories_approval = True
      elif re.match("^([-]1|reject|rejected)$", first_line, re.I):
        for sign in CMSSW_L2[commenter]:
          signatures[sign] = "rejected"
          has_categories_approval = False

    # Some of the special users can say "hold" prevent automatic merging of
    # fully signed PRs.
    if commenter in CMSSW_L1 + CMSSW_L2.keys() + releaseManagers:
      if re.match("^hold$", first_line, re.I):
        is_hold = True
        blocker = commenter

  print "The labels of the pull request should be:"
  # Labels coming from signature.
  labels = [x + "-pending" for x in signing_categories]

  for category, value in signatures.items():
    if not category in signing_categories:
      continue
    labels = [l for l in labels if not l.startswith(category+"-")]
    if value == "approved":
      labels.append(category + "-approved")
    elif value == "rejected":
      labels.append(category + "-rejected")
    elif value == "started":
       labels.append(category + "-started")
    else:
      labels.append(category + "-pending")

  # Additional labels.
  if is_hold:
    labels.append("hold")

  if cmssw_repo:
    if comparison_done:
      labels.append("comparison-available")
    else:
      labels.append("comparison-pending")

  print "\n".join(labels)

  # Now updated the labels.
  missingApprovals = [x
                      for x in labels
                      if not x.endswith("-approved")
                         and not x.startswith("orp")
                         and not x.startswith("tests")
                         and not x.startswith("comparison")
                         and not x == "hold"]

  if not missingApprovals:
    print "The pull request is complete."
  if missingApprovals:
    labels.append("pending-signatures")
  else:
    labels.append("fully-signed")
  labels = set(labels)

  # We update labels only if they are different.
  SUPER_USERS = (yaml.load(file("super-users.yaml")))
  old_labels = set([x.name for x in issue.labels])
  releaseManagersList = ", ".join(["@" + x for x in set(releaseManagers + SUPER_USERS)])
  releaseManagersMsg = ""
  if releaseManagers:
    releaseManagersMsg = format("%(rm)s can you please take care of it?",
                                 rm=releaseManagersList)

  #For now, only trigger tests for cms-sw/cmssw
  if cmssw_repo:
    # trigger the tests and inform it in the thread.
    if trigger_test_on_signature and has_categories_approval:
      tests_requested = True
    if tests_requested:
      if not dryRun:
        pr.create_issue_comment( TRIGERING_TESTS_MSG )
        create_properties_file_tests( prId, dryRun )

  # Do not complain about tests
  requiresTestMessage = " after it passes the integration tests"
  if "tests-approved" in labels:
    requiresTestMessage = " (tests are also fine)"
  elif "tests-rejected" in labels:
    requiresTestMessage = " (but tests are reportedly failing)"

  autoMergeMsg = ""
  if all(["fully-signed"     in labels,
          not "hold"         in labels,
          not "orp-rejected" in labels,
          not "orp-pending"  in labels,
          "tests-approved"   in labels]):
    autoMergeMsg = "This pull request will be automatically merged."
  else:
    if "orp-pending" in labels or "orp-rejected" in labels:
      autoMergeMsg = format("This pull request requires discussion in the"
                            " ORP meeting before it's merged. %(managers)s",
                            managers=releaseManagersList)
    elif "new-package-pending" in labels:
      autoMergeMsg = format("This pull request requires a new package and "
                            " will not be merged. %(managers)s",
                            managers=releaseManagersList)
    elif "hold" in labels:
      autoMergeMsg = format("This PR is put on hold by @%(blocker)s. He / she"
                            " will have to remove the `hold` comment or"
                            " %(managers)s will have to merge it by"
                            " hand.",
                            blocker=blocker,
                            managers=releaseManagersList)

  devReleaseRelVal = ""
  if pr.base.ref in DEVEL_RELEASE_CYCLE:
    devReleaseRelVal = " and once validation in the development release cycle "+DEVEL_RELEASE_CYCLE[pr.base.ref]+" is complete"
  messageFullySigned = format("This pull request is fully signed and it will be"
                              " integrated in one of the next %(branch)s IBs"
                              "%(requiresTest)s"
                              "%(devReleaseRelVal)s."
                              " %(autoMerge)s",
                              requiresTest=requiresTestMessage,
                              autoMerge = autoMergeMsg,
                              devReleaseRelVal=devReleaseRelVal,
                              branch=pr.base.ref)

  if old_labels == labels:
    print "Labels unchanged."
  elif not dryRun:
    issue.edit(labels=list(labels))
    diff_labels1 = old_labels-labels
    diff_labels2 = labels-old_labels
    if (diff_labels1==set(["tests-pending"])) and (diff_labels2==set(["tests-started"])):
      pass
    elif all(["fully-signed" in labels,
            not "orp-approved" in labels,
            not "orp-pending" in labels]):
      pr.create_issue_comment(messageFullySigned)
    elif "fully-signed" in labels and "orp-approved" in labels:
      pass
    elif "fully-signed" in labels and "orp-pending" in labels:
      pr.create_issue_comment(messageFullySigned)

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
    releaseManagersMsg = format("%(managers)s you are the release manager for"
                                " this.\nYou can merge this pull request by"
                                " typing 'merge' in the first line of your"
                                " comment.",
                                managers = managers)

  # Construct message for ORP approval
  orpRequiredMsg = ""
  if requiresL1:
    orpRequiredMsg = format("\nThis pull requests was done for a production"
                            " branch and will require explicit ORP approval"
                            " on friday or L1 override.")

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
                         "release cycle, please use the %(base_branch)s branch instead",
                         base_rel=base_release,
                         base_branch=base_release_branch)

    # We do not want to spam people for the old pull requests.
    messageNewPR = format("A new Pull Request was created by @%(user)s"
                        " %(name)s for %(branch)s.\n\n"
                        "%(title)s\n\n"
                        "It involves the following packages:\n\n"
                        "%(packages)s\n\n"
                        "%(new_package_message)s\n"
                        "%(l2s)s can you please review it and eventually sign?"
                        " Thanks.\n"
                        "%(watchers)s"
                        "You can sign-off by replying to this message having"
                        " '+1' in the first line of your reply.\n"
                        "You can reject by replying  to this message having"
                        " '-1' in the first line of your reply.\n"
                        "If you are a L2 or a release manager you can ask for"
                        " tests by saying 'please test' or '@cmsbuild, please test'"
                        " in the first line of a comment.\n"
                        "%(releaseManagers)s"
                        "%(orpRequired)s"
                        "\n%(patch_branch_warning)s",
                        user=pr.user.login,
                        name=pr.user.name and "(%s)" % pr.user.name or "",
                        branch=pr.base.ref,
                        title=pr.title.encode("ascii", "ignore"),
                        l2s=", ".join(missing_notifications),
                        packages="\n".join(packages),
                        new_package_message=new_package_message,
                        watchers=watchersMsg,
                        releaseManagers=releaseManagersMsg,
                        orpRequired=orpRequiredMsg,
                        patch_branch_warning=warning_msg)

    messageUpdatedPR = format("Pull request #%(pr)s was updated."
                            " %(signers)s can you please check and sign again.",
                            pr=pr.number,
                            signers=", ".join(missing_notifications))
  else:
    if create_external_issue:
      if not already_seen:
        if dryRun:
          print "Should create a new issue in ",external_issue_repo_name," for this PR"
        else:
          external_managers = ["@" + name for name, l2_categories in CMSSW_L2.items() if "externals" in l2_categories]
          cmsdist_repo  = gh.get_repo(external_issue_repo_name)
          cmsdist_title = format("%(repo)s#%(pr)s: %(title)s",
                                 title=pr.title.encode("ascii", "ignore"),
                                 repo=repository,
                                 pr=pr.number)
          cmsdist_body = format("A new Pull Request was created by @%(user)s"
                                " %(name)s for branch %(branch)s.\n\n"
                                "Pull Request Reference: %(repo)s#%(pr)s\n\n"
                                "%(externals_l2s)s can you please review it and eventually sign? Thanks.\n",
                                repo=repository,
                                user=pr.user.login,
                                name=pr.user.name and "(%s)" % pr.user.name or "",
                                branch=pr.base.ref,
                                externals_l2s=", ".join(external_managers),
                                pr=pr.number)
          cissue = cmsdist_repo.create_issue(cmsdist_title, cmsdist_body)
          external_issue_number = str(cissue.number)
          print "Created a new issue ",external_issue_repo_name,"#",external_issue_number
      if pull_request_updated and external_issue_number:
        if dryRun:
          print "Should add an update message for issue ",external_issue_repo_name,"#",external_issue_number
        else:
          cmsdist_repo  = gh.get_repo(external_issue_repo_name)
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
      cmsdist_issue="\n\nexternal issue "+external_issue_repo_name+"#"+external_issue_number

    messageNewPR = format("A new Pull Request was created by @%(user)s"
                          " %(name)s for branch %(branch)s.\n\n"
                          "%(title)s\n\n"
                          "%(l2s)s can you please review it and eventually sign?"
                          " Thanks.\n"
                          "%(watchers)s"
                          "You can sign-off by replying to this message having"
                          " '+1' in the first line of your reply.\n"
                          "You can reject by replying  to this message having"
                          " '-1' in the first line of your reply."
                          "%(cmsdist_issue)s",
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
  if pr.base.ref in RELEASE_BRANCH_CLOSED:
    commentMsg = messageBranchClosed
  elif not already_seen:
    commentMsg = messageNewPR
  elif pull_request_updated:
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
    pr.create_issue_comment(commentMsg)

  # Check if it needs to be automatically closed.
  if mustClose == True and issue.state == "open":
    print "This pull request must be closed."
    if not dryRun:
      print issue.edit(state="closed")

  # Check if it needs to be automatically merged.
  if all(["fully-signed" in labels,
          "tests-approved" in labels,
          not "hold" in labels,
          not "orp-rejected" in labels,
          not "orp-pending" in labels,
          not "new-package-pending" in labels]):
    print "This pull request can be automatically merged"
    mustMerge = True
  else:
    print "This pull request will not be automatically merged."
    print not "orp-rejected" in labels, not "orp-pending" in labels

  if mustMerge == True:
    print "This pull request must be merged."
    if not dryRun:
        try:
          pr.merge()
        except:
          pass

