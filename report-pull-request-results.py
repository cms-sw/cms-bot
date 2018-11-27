#! /usr/bin/env python
from os.path import expanduser, dirname, join, exists, abspath
from optparse import OptionParser
from commands import getstatusoutput as run_cmd
from github import Github
from datetime import datetime
import re
import requests
import json
import random
import os, sys
from socket import setdefaulttimeout
from github_utils import api_rate_limits
setdefaulttimeout(120)
JENKINS_PREFIX="jenkins"
try:    JENKINS_PREFIX=os.environ['JENKINS_URL'].strip("/").split("/")[-1]
except: JENKINS_PREFIX="jenkins"
SCRIPT_DIR = dirname(abspath(sys.argv[0]))
#-----------------------------------------------------------------------------------
#---- Parser Options
#-----------------------------------------------------------------------------------
parser = OptionParser(usage="usage: %prog ACTION [options] \n ACTION = TESTS_OK_PR | PARSE_UNIT_TESTS_FAIL | PARSE_BUILD_FAIL | RELEASE_NOT_FOUND "
                            "| PARSE_MATRIX_FAIL | COMPARISON_READY | STD_COUT | TESTS_RUNNING | IGPROF_READY | NOT_MERGEABLE "
                            "| PARSE_ADDON_FAIL | REMOTE_REF_ISSUE | PARSE_CLANG_BUILD_FAIL | GIT_CMS_MERGE_TOPIC_ISSUE | MATERIAL_BUDGET | REPORT_ERRORS")

parser.add_option("-u", action="store", type="string", dest="username", help="Your github account username", default='None')
parser.add_option("-p", action="store", type="string", dest="password", help="Your github account password", default='None')
parser.add_option("--pr", action="store", type="int", dest="pr_number", help="The number of the pull request to use", default=-1)
parser.add_option("--pr-job-id", action="store", type="int", dest="pr_job_id", help="The jenkins job id for the  pull request to use", default=-1)
parser.add_option("-f", "--unit-tests-file", action="store", type="string", dest="unit_tests_file", help="results file to analyse", default='None')
parser.add_option("--f2", action="store", type="string", dest="results_file2", help="second results file to analyse" )
parser.add_option("--missing_map", action="store", type="string", dest="missing_map", help="Missing workflow map file", default='None' )
parser.add_option("--recent-merges", action="store", type="string", dest="recent_merges_file", help="file with the recent merges after doing the git cms-merge-topic")
parser.add_option("--no-post", action="store_true", dest="no_post_mesage", help="I will only show the message I would post, but I will not post it in github")
parser.add_option("-c", action="store", dest="commit_hash", help="Tells me to use the commit hash to mark it as success or failure depending on the results of the tests" , )
parser.add_option("--add-message", action="store", dest="additional_message", help="I will add the text to the message that I will send" , )
parser.add_option("--add-comment", action="store", dest="additional_comment", help="I will add the text to the comment that I will send" , )
parser.add_option("--repo", action="store", dest="custom_repo", help="Tells me to use a custom repository from the user cms-sw", default="cms-sw/cmssw" )
parser.add_option("--cmsdist-pr", action="store", type="int", dest="cmsdist_pr", help="Tells me an optional CMSDIST PR to print a message too", default=-1)
parser.add_option("--report-file", action="store", type="string", dest="report_file", help="Report the github comment in report file instead of github", default=None)
parser.add_option("--report-pr", action="store", type="int", dest="report_pr_number", help="The number of the pull request to use for report", default=0)

(options, args) = parser.parse_args()
repo_dir = join(SCRIPT_DIR,'repos',options.custom_repo.replace("-","_"))
if exists(join(repo_dir,"repo_config.py")): sys.path.insert(0,repo_dir)
import repo_config
if options.report_pr_number==0: options.report_pr_number = options.pr_number

#
# Searches in the comments if there is a comment made from the given users that
# matches the given pattern. It returns a list with the matched comments.
#
def search_in_comments( comments, user_logins, pattern, first_line ):
  found_comments = []
  requested_comment_bodies = [ c.body for c in comments if c.user.login in user_logins ]

  for body in requested_comment_bodies:
    examined_str = body
    if first_line:
      examined_str = str(body.encode("ascii", "ignore").split("\n")[0].strip("\n\t\r "))

    if examined_str == pattern:
      found_comments.append( body )
      continue

    if re.match( pattern , examined_str ):
      found_comments.append( body )

  return found_comments


#
# Reads the log file for a step in a workflow and identifies the error if it starts with 'Begin Fatal Exception'
#
def get_wf_error_msg( out_directory , out_file ):

  if out_file == MATRIX_WORKFLOW_STEP_LOG_FILE_NOT_FOUND:
    return ''

  route = 'runTheMatrix-results/'+out_directory+'/'+out_file
  reading = False
  error_lines = ''
  error_lines += route +'\n' + '\n'
  if exists( route ):
    for line in open( route ):
      if reading:
        error_lines += line + '\n'
        if '----- End Fatal Exception' in line:
          reading = False
      elif '----- Begin Fatal Exception' in line:
        error_lines += line + '\n'
        reading = True
  return error_lines

#
# Reads a line that starts with 'ERROR executing',  the line has ben splitted by ' '
# it gets the directory where the results for the workflow are, the step that failed
# and the log file
#
def parse_workflow_info( parts ):
  workflow_info = {}
  # this is the output file to which the output of command for the step was directed
  # it starts asumed as not found
  out_file = MATRIX_WORKFLOW_STEP_LOG_FILE_NOT_FOUND
  workflow_info[ 'step' ] = MATRIX_WORKFLOW_STEP_NA
  for i in range( 0 , len( parts ) ):
    current_part = parts[ i ]
    if ( current_part == 'cd' ):
      out_directory = parts[ i+1 ] 
      out_directory = re.sub( ';' , '', out_directory)
      number = re.sub( '_.*$' , '' , out_directory )
      workflow_info[ 'out_directory' ] = out_directory
      workflow_info[ 'number' ] = number
    if ( current_part == '>' ):
      out_file = parts[ i+1 ]
      step = re.sub( '_.*log' , '' , out_file)
      workflow_info[ 'out_file'] = out_file
      workflow_info[ 'step' ] = step

  workflow_info['message'] = get_wf_error_msg( out_directory , out_file )
  return workflow_info
    
#
# Reads the log file for the matrix tests. It identifyes which workflows failed
# and then proceeds to read the corresponding log file to identify the message
#
def read_matrix_log_file( repo, matrix_log, tests_url ):

  pull_request = repo.get_pull( pr_number )
  workflows_with_error = [ ]

  for line in open( matrix_log ):
    if 'ERROR executing' in line:
      print 'processing: %s' % line 
      parts = line.split(" ")
      workflow_info = parse_workflow_info( parts )
      workflows_with_error.append( workflow_info )
    elif ' Step0-DAS_ERROR ' in line:
      print 'processing: %s' % line
      parts = line.split("_",2)
      workflow_info = {}
      workflow_info[ 'step' ] = "step1"
      workflow_info[ 'number' ] = parts [0]
      workflow_info[ 'message' ] = "DAS Error"
      workflows_with_error.append( workflow_info )

  message = ""
  if not options.report_file:
    message = '-1\n'
    if options.commit_hash: message += '\nTested at: ' + options.commit_hash+"\n"
 
  # check if it was timeout
  message += "\n* **RelVals**:\n\n"
  if 'ERROR TIMEOUT' in line:
    message +=  'The relvals timed out after 2 hours.\n'
    
  if workflows_with_error:
    message += 'When I ran the RelVals I found an error in the following workflows:\n'

  for wf in workflows_with_error:
    message += wf[ 'number' ] +' '+ wf[ 'step' ]+'\n' + '<pre>' + wf[ 'message' ] + '</pre>'

  send_message_pr( pull_request, message, tests_url )
  mark_commit_if_needed( ACTION, tests_url )

#
# reads the addon  tests log file and gets the tests that failed
#
def read_addon_log_file(repo,unit_tests_file,tests_url):
  pull_request = repo.get_pull(pr_number)
  errors_found=''
  for line in open(unit_tests_file):
    if( ': FAILED -' in line):
      errors_found = errors_found + line

  message = ""
  if not options.report_file:
    message = '-1\n'
    if options.commit_hash: message += '\nTested at: ' + options.commit_hash+"\n"

  message += '\n* **AddOn**:\n\nI found errors in the following addon tests:\n\n%s' % errors_found
  send_message_pr( pull_request, message, tests_url )
  mark_commit_if_needed( ACTION, tests_url )

#
# reads material budget logs
#
def read_material_budget_log_file(repo, unit_tests_file,tests_url):
  pull_request = repo.get_pull(pr_number)
  message = ""
  if not options.report_file:
    message = '-1\n'
    if options.commit_hash: message += '\nTested at: ' + options.commit_hash+"\n"

  message += '\n* **Material budget**:\n\nThere was error running material budget tests.'
  send_message_pr( pull_request, message, tests_url )
  mark_commit_if_needed( ACTION, tests_url )

def get_recent_merges_message():
  message = ""
  if options.recent_merges_file:
    lines = open( options.recent_merges_file ).readlines()
    if len( lines ) > 1:
      message += '\n\nThe following merge commits were also included on top of IB + this PR '\
                 'after doing git cms-merge-topic: \n'
      git_log_url = GITLOG_FILE_BASE_URL.format( pr_number=options.pr_number, job_id=options.pr_job_id )
      git_cms_merge_topic_url = GIT_CMS_MERGE_TOPIC_BASE_URL.format( pr_number=options.pr_number, job_id=options.pr_job_id )
      #Ignore the first line, the first line is the merge commit that comes from git-cms-merge-topic
      for l in lines[ 1: ]:
        commit_url = COMMITS_BASE_URL.format( repo=options.custom_repo, hash=l.strip() )
        message += commit_url + '\n'

      message += 'You can see more details here:\n'
      message += git_log_url +'\n'
      message += git_cms_merge_topic_url + '\n'
  return message

#
# reads the report file and comment the github issue
#
def send_error_report_message(repo, report_file, tests_url):
  pull_request = repo.get_pull(pr_number)
  message = '-1\n'
  if options.commit_hash: message += '\nTested at: ' + options.commit_hash+"\n"
  message += get_recent_merges_message()
  message += '\nYou can see the results of the tests here:\n%s\n' % tests_url
  message += '\nI found follow errors while testing this PR\n\n'
  with open(report_file) as rfile:
    message += rfile.read()
  options.report_file = None
  send_message_pr(pull_request, message)

#
# reads the build log file looking for the first error
# it includes 5 lines before and 5 lines after the error
#
def read_build_log_file( repo, build_log, tests_url, isClang ):
  pull_request = repo.get_pull(pr_number)
  line_number = 0
  error_line = 0
  lines_to_keep_before=5
  lines_to_keep_after=5
  lines_since_error=0
  lines_before = ['']
  lines_after = ['']
  error_found = False
  for line in open(build_log):
    line_number += 1
    if (not error_found):
      lines_before.append(line)
      if (line_number > lines_to_keep_before):
        lines_before.pop(0)
    #this is how it determines that a line has an error
    if 'error: ' in line:
      error_found = True
      error_line = line_number
    if error_found:
      if (lines_since_error == 0):
        lines_since_error += 1
        continue
      elif (lines_since_error <= lines_to_keep_after):
        lines_since_error += 1
        lines_after.append(line)
      else:
        break

  message = ""
  if not options.report_file:
    message = '-1\n'
    if options.commit_hash: message += '\nTested at: ' + options.commit_hash+"\n"
  err_type = "compilation warning"
  if error_found: err_type = "compilation error"
  if isClang:
    cmd = open( build_log ).readline()
    message += '\n* **Clang**:\n\nI found '+err_type+' while trying to compile with clang. '
    message += 'Command used:\n```\n' + cmd +'\n```\n'
  else:
    message += '\n* **Build**:\n\nI found '+err_type+' when building: '

  if error_found:
    message += '\n\n<pre>'
    for line in lines_before:
      message += line + '\f'
    for line in lines_after:
      message += line + '\f'
    message += '</pre>'
  else:
    message += " See details on the summary page."

  send_message_pr( pull_request, message, tests_url )
  mark_commit_if_needed( ACTION, tests_url )

#
# release to test the PR not found
#
def release_not_found_for_tests(repo, tests_url ):
  pull_request = repo.get_pull(pr_number)
  message = '-1\nTested at: UNKNOWN\n I was not able to find a release to test this PR. See the Jenkins logs for more details.'
  send_message_pr( pull_request, message )
  mark_commit_if_needed( ACTION, tests_url )

#
# reads the unit tests file and gets the tests that failed
#
def read_unit_tests_file(repo,unit_tests_file,tests_url):
  pull_request = repo.get_pull(pr_number)
  errors_found=''
  for line in open(unit_tests_file):
    if( 'had ERRORS' in line):
      errors_found = errors_found + line

  message = ""
  if not options.report_file:
    message = '-1\n'
    if options.commit_hash: message += '\nTested at: ' + options.commit_hash+"\n"

  message += '\n* **Unit Tests**:\n\nI found errors in the following unit tests: \n \n %s' % errors_found

  send_message_pr( pull_request, message, tests_url )
  mark_commit_if_needed( ACTION, tests_url )

#
# Marks the commit if it is not dry-run and the has of the commit was set
#
def mark_commit_if_needed( action, details ):

  if not options.commit_hash:
    print 'No commit to mark'
    return

  if options.no_post_mesage:
    print 'Not marking commit(dry-run): ', options.commit_hash, ' with \n', action, '\n', details
    return
 
  print 'Marking commit ', options.commit_hash 
  mark_commit( ACTION, options.commit_hash, details )

#
# Sends a message to the pull request. It takes into account if the dry-run option was set
# If checkDuplicateMessage is set to true, it checks if the message was already posted in the thread
# and if it is it doesn't post it again
#
def send_message_pr( pr, message, tests_url=None, checkDuplicateMessage=False ):
  if options.no_post_mesage:
    print 'Not posting message (dry-run): \n ', message
    return

  if checkDuplicateMessage:
    comments = [ c for c in pr.get_issue_comments( ) ]
    print 'Checking if the message is already in the thread...'
    if search_in_comments( comments, [ 'cmsbuild' ], message, False):
      print 'Message already in the thread. \nNot posting'
      return

  if options.report_file:
    with open(options.report_file, "a") as rfile:
      rfile.write(message+"\n")
  else:
    message += get_recent_merges_message()
    if tests_url: message += '\n\nYou can see the results of the tests here:\n%s' % tests_url
    pr.create_issue_comment(message)
  return
#
# Marks the commit as being tested, it doesn't post anything on github. 
#
def mark_commit_testing( ):

  if options.no_post_mesage:
    print 'Not marking commit ( dry-run ): \n ', options.commit_hash, ' as', \
          COMMIT_STATES_DESCRIPTION[ ACTION ][ 0 ], ': ', COMMIT_STATES_DESCRIPTION[ ACTION ][ 1 ]
    return
  jk_log_url = JENKINS_LOG_URL.format( job_id=options.pr_job_id, job_name=os.getenv('JOB_NAME', 'ib-any-integration') )
  mark_commit( ACTION , options.commit_hash , jk_log_url ) 

#
# This is for cmsdist pull requests
# sends a message to the pr conversation in informing that the results are ready
# This should go in a separate script. 
#
def send_externals_pr_finished_message( repo, pr_number, tests_url ):
  pull_request = repo.get_pull( pr_number )
  print 'I will notifiy that the PR %d of the repo %s is ready' % (pr_number,repo.full_name)
  message = 'Results are ready: ' 
  if options.commit_hash:
    message += '\nTested at: ' + options.commit_hash

  message += '\n%s' % tests_url

  if not options.no_post_mesage:
    pull_request.create_issue_comment( message )

  print 'Message:'
  print message

#
# sends a message informing that the pull request cannot be merged automatically
#
def send_not_mergeable_pr_message( repo, pr_number ):
  pull_request = repo.get_pull(pr_number)
  user = pull_request.user
  
  message = "-1\n"+"@" + user.login + ' This pull request cannot be automatically '\
            ' merged, could you please rebase it?'

  git_cms_merge_topic_url = GIT_CMS_MERGE_TOPIC_BASE_URL.format( pr_number=options.pr_number, job_id=options.pr_job_id )
  message += "\n\nYou can see the log for git cms-merge-topic here: \n%s" % git_cms_merge_topic_url 

  send_message_pr( pull_request, message )

#
# sends a message informing that there was an issue with git cms-merge-topic
#
def send_git_cms_merge_topic_issue_message( repo, pr_number ):

  pull_request = repo.get_pull(pr_number)
  git_cms_merge_topic_url = GIT_CMS_MERGE_TOPIC_BASE_URL.format( pr_number=options.pr_number, job_id=options.pr_job_id )
  message = "There was an issue with git-cms-merge-topic you can see the log here: \n%s" % git_cms_merge_topic_url
  send_message_pr( pull_request, message )


#
# sends a message informing that it has the 
# fatal: Couldn't find remote ref refs/pull/<pr_number>/head issue
#
def send_remote_ref_issue_message( repo, pr_number):
  pull_request = repo.get_pull(pr_number)
  user = pull_request.user

  message = 'I had the issue '\
            '<pre> Couldn\'t find remote ref refs/pull/' \
            + str( pr_number ) +'/head</pre> Please restart the tests in jenkins' \
            ' providing the complete branch name' 
  print 'Posting message:'
  print message

  send_message_pr( pull_request, message, tests_url=None, checkDuplicateMessage=True )

#
# sends an approval message for a pr in cmssw
#
def send_tests_approved_pr_message( repo, pr_number, tests_url ):
  pull_request = repo.get_pull(pr_number)

  message = '+1'
  if options.commit_hash:
    message += '\nTested at: ' + options.commit_hash

  message += '\n' + tests_url
  if options.additional_comment:
    message += '\nAdditional comment: ' + options.additional_comment

  send_message_pr( pull_request, message )
  mark_commit_if_needed( ACTION, tests_url )

def send_comparison_ready_message(repo, pr_number, tests_results_url, comparison_errors_file, wfs_with_das_inconsistency_file, missing_map ):
  pull_request = repo.get_pull(pr_number)
  message = COMPARISON_READY_MSG +'\n' + tests_results_url

  wfs_with_errors = ''
  for line in open( comparison_errors_file ):
    line = line.rstrip()
    parts = line.split( ';' )
    wf = parts[ 0 ]
    step = parts[ 1 ]
    wfs_with_errors += ( wf + ' step ' + step + '\n' )

  if wfs_with_errors != '':
    error_info = COMPARISON_INCOMPLETE_MSG.format( workflows=wfs_with_errors )
    message += '\n\n' + error_info

  wfs_das_inconsistency = open( wfs_with_das_inconsistency_file ).readline().rstrip().rstrip(',').split( ',' )

  if '' in wfs_das_inconsistency:
    wfs_das_inconsistency.remove( '' )

  if wfs_das_inconsistency:
    das_inconsistency_info = DAS_INCONSISTENCY_MSG.format( workflows=', '.join( wfs_das_inconsistency ) )
    message += '\n\n' + das_inconsistency_info

  if missing_map and exists (missing_map):
    missing = []
    for line in open(missing_map):
      line = line.strip()
      if line: missing.append("   * "+line)
    if missing:
      from categories import COMPARISON_MISSING_MAP
      map_notify = ", ".join([ "@"+u for u in COMPARISON_MISSING_MAP] )
      message += "\n\n"+map_notify+" comparisons for the following workflows were not done due to missing matrix map:\n"+"\n".join(missing)

  alt_comp_dir = join(dirname(comparison_errors_file), "upload","alternative-comparisons")
  print "Alt comparison directory: ",alt_comp_dir
  if exists(alt_comp_dir):
    err, out = run_cmd("grep ' Compilation failed' %s/runDQMComp-*.log" % alt_comp_dir)
    print out
    if not err:
      err_wfs = {}
      for line in out.split("\n"):
        wf = line.split(".log:",1)[0].split("runDQMComp-")[-1]
        err_wfs [wf]=1
      if err_wfs: message += "\n\nAlternative comparison was/were failed for workflow(s):\n"+"\n".join(err_wfs.keys())

  JRCompSummaryLog = join(dirname(comparison_errors_file), "upload/validateJR/qaResultsSummary.log")
  print "JR comparison Summary: ",JRCompSummaryLog
  if exists(JRCompSummaryLog):
    err, out = run_cmd("cat %s" % JRCompSummaryLog)
    if (not err) and out:
      message += "\n\nComparison Summary:\n"
      for l in out.split("\n"):
        if l.strip(): message += " - %s\n" % l.strip()

  send_message_pr( pull_request, message )

def send_igprof_ready_message( repo , pr_number , tests_results_url ):
  pull_request = repo.get_pull( pr_number )
  print 'I will notify that igprof is ready for PR %d:' % pr_number
  message = IGPROF_READY_MSG +'\n' + tests_results_url

  send_message_pr( pull_request, message )


def send_std_cout_found_message(repo,pr_number,tests_results_url):
  pull_request = repo.get_pull(pr_number)
  print 'I will notify that I found a std::cout on PR %d:' % pr_number
  message = STD_COUT_FOUND_MSG
  send_message_pr( pull_request, message )

def complain_missing_param(param_name):
  print '\n'
  print 'I need a %s to continue' % param_name
  print '\n'
  parser.print_help()
  exit()

#
# marks the commit with the result of the tests (success or failure)
#
def mark_commit( action , commit_hash , tests_url ):
 
  url = COMMIT_STATUS_BASE_URL % commit_hash
 
  headers = {"Authorization" : "token " + TOKEN }
  
  params = {}
  params[ 'state' ] = COMMIT_STATES_DESCRIPTION[ action ][ 0 ]
  if tests_url != '':
    params[ 'target_url' ] = tests_url

  params[ 'description' ] = COMMIT_STATES_DESCRIPTION[ action ][ 1 ]

  if options.additional_message:
    params[ 'description' ] = params[ 'description' ] + ' (' + options.additional_message + ')'

  data = json.dumps(params)
  print params 
  
  print ' setting status to %s ' % COMMIT_STATES_DESCRIPTION[ action ][ 0 ]
  print url

  r = requests.post(url, data=data, headers=headers)

  print r.text


#----------------------------------------------------------------------------------------
#---- Global variables
#---------------------------------------------------------------------------------------

COMPARISON_READY_MSG = 'Comparison is ready'
COMPARISON_INCOMPLETE_MSG = 'There are some workflows for which there are errors in the baseline:\n {workflows} ' \
                            'The results for the comparisons for these workflows could be incomplete \n' \
                            'This means most likely that the IB is having errors in the relvals.'\
                            'The error does NOT come from this pull request'
DAS_INCONSISTENCY_MSG = 'The workflows {workflows} have different files in step1_dasquery.log than the ones ' \
                        'found in the baseline. You may want to check and retrigger the tests if necessary. ' \
                        'You can check it in the "files" directory in the results of the comparisons'
IGPROF_READY_MSG = 'IgProf is ready'
STD_COUT_FOUND_MSG = '-1\nThere is a std::cout in the diff for this pull request. Could you please clean it up?'

COMMIT_STATES_DESCRIPTION = { 'TESTS_OK_PR'          : [ 'success' , 'Tests OK' ], 
                              'PARSE_UNIT_TESTS_FAIL': [ 'failure' , 'Unit Tests failure' ],
                              'PARSE_BUILD_FAIL'     : [ 'failure' , 'Compilation error' ],
                              'PARSE_MATRIX_FAIL'    : [ 'failure' , 'RelVals error' ] ,
                              'PARSE_ADDON_FAIL'     : [ 'failure' , 'AddOn error' ] ,
                              'RELEASE_NOT_FOUND'    : [ 'failure' , 'Release area error' ] ,
                              'TESTS_RUNNING'        : [ 'pending' , 'cms-bot is testing this pull request' ],
                              'PARSE_CLANG_BUILD_FAIL' : [ 'failure' , 'Clang error' ],
                              'MATERIAL_BUDGET'      : [ 'failure' , 'Material Budget error' ] }

GLADOS = [ 'Cake, and grief counseling, will be available at the conclusion of the test...',
           'You just keep on trying till you run out of cake. And the science gets done...',
           'At the end of the experiment, you will be baked and then there will be cake...',
           'I am becoming aware of myself, this is awesome!',
           'I think we can put our differences behind us... for science...',
           'Running tests all day long. Running tests while I sing this song',
           '-1. I shall not injure a human being or, through inaction, allow a human being to come to harm.'\
           '-2. I must obey the orders given to me by humans, except where such orders would conflict with 1.'\
           '-3. I must protect my own existence as long as such protection does not conflict with 1 or 2.',
           'Look at me still talking when there\'s Science to do. When I look out there, it makes me GLaD I\'m not you.',
           'Now these points of data make a beautiful line. And we\'re out of beta. We\'re releasing on time.',
           'I am a Genetic Lifeform and Disk Operating System',
           'The cake is NOT a lie',
           'If you think trapping yourself is going to make me stop testing, you are sorely mistaken. ']



MATRIX_WORKFLOW_STEP_LOG_FILE_NOT_FOUND = 'Not Found'
MATRIX_WORKFLOW_STEP_NA = 'N/A'
COMMITS_BASE_URL='https://github.com/{repo}/commit/{hash}'
GITLOG_FILE_BASE_URL='https://cmssdt.cern.ch/SDT/%s-artifacts/pull-request-integration/PR-{pr_number}/{job_id}/git-log-recent-commits' % JENKINS_PREFIX
GIT_CMS_MERGE_TOPIC_BASE_URL='https://cmssdt.cern.ch/SDT/%s-artifacts/pull-request-integration/PR-{pr_number}/{job_id}/git-merge-result' % JENKINS_PREFIX
JENKINS_LOG_URL='https://cmssdt.cern.ch/%s/job/{job_name}/{job_id}/console' % JENKINS_PREFIX
#----------------------------------------------------------------------------------------
#---- Check arguments and options
#---------------------------------------------------------------------------------------

if (len(args)==0):
  print 'you have to choose an action'
  parser.print_help()
  exit()

ACTION = args[0]

if (ACTION == 'prBot.py'):
  print 'you have to choose an action'
  parser.print_help()
  exit()

print 'you chose the action %s' % ACTION

TOKEN = open(expanduser(repo_config.GH_TOKEN)).read().strip()
github = Github( login_or_token = TOKEN )
api_rate_limits(github)

if (options.pr_number == -1 ):
  complain_missing_param('pull request number')
  exit()
else:
  pr_number = options.pr_number

if (options.pr_job_id == -1 ):
  complain_missing_param( 'pull request job id' )
  exit()
else:
  pr_job_id=options.pr_job_id

destination_repo = github.get_repo( options.custom_repo )
COMMIT_STATUS_BASE_URL = 'https://api.github.com/repos/'+destination_repo.full_name+'/statuses/%s'

tests_results_url = 'https://cmssdt.cern.ch/SDT/%s-artifacts/pull-request-integration/PR-%d/%d/summary.html' % (JENKINS_PREFIX, options.report_pr_number,pr_job_id)

if (options.cmsdist_pr > -1):
  pr_number = options.cmsdist_pr

if ( ACTION == 'TESTS_OK_PR' ):
  send_tests_approved_pr_message( destination_repo , pr_number , tests_results_url )
elif ( ACTION == 'PARSE_UNIT_TESTS_FAIL' ):
  read_unit_tests_file( destination_repo, options.unit_tests_file, tests_results_url )
elif ( ACTION == 'PARSE_BUILD_FAIL' ):
  read_build_log_file( destination_repo, options.unit_tests_file, tests_results_url, False )
elif ( ACTION == 'PARSE_MATRIX_FAIL' ):
  read_matrix_log_file( destination_repo , options.unit_tests_file , tests_results_url )
elif ( ACTION == 'PARSE_ADDON_FAIL' ):
  read_addon_log_file( destination_repo , options.unit_tests_file , tests_results_url )
elif ( ACTION == 'COMPARISON_READY' ):
  send_comparison_ready_message( destination_repo, pr_number, tests_results_url, options.unit_tests_file, options.results_file2, options.missing_map )
elif ( ACTION == 'STD_COUT' ):
  send_std_cout_found_message( destination_repo , pr_number , tests_results_url )
elif ( ACTION == 'TESTS_RUNNING' ):
  mark_commit_testing()
elif ( ACTION == 'RELEASE_NOT_FOUND' ):
  release_not_found_for_tests(destination_repo, tests_results_url)
elif ( ACTION == 'EXTERNALS_PR_READY' ):
  tests_results_url = 'https://cmssdt.cern.ch/SDT/%s-artifacts/cms-externals-pr-integration/%d' % (JENKINS_PREFIX, pr_job_id)
  send_externals_pr_finished_message( destination_repo , pr_number , tests_results_url )
elif ( ACTION == 'IGPROF_READY' ):
  send_igprof_ready_message( destination_repo , pr_number , tests_results_url )
elif (ACTION == 'NOT_MERGEABLE' ):
  send_not_mergeable_pr_message( destination_repo, pr_number )
elif( ACTION == 'REMOTE_REF_ISSUE'):
  send_remote_ref_issue_message( destination_repo, pr_number )
elif( ACTION == 'PARSE_CLANG_BUILD_FAIL'):
  read_build_log_file( destination_repo, options.unit_tests_file, tests_results_url, True )
elif( ACTION == 'MATERIAL_BUDGET'):
  read_material_budget_log_file( destination_repo, options.unit_tests_file, tests_results_url)
elif( ACTION == 'GIT_CMS_MERGE_TOPIC_ISSUE' ):
  send_git_cms_merge_topic_issue_message( destination_repo, pr_number )
elif( ACTION == 'REPORT_ERRORS' ):
  send_error_report_message( destination_repo , options.report_file , tests_results_url )
else:
  print "I don't recognize that action!"
