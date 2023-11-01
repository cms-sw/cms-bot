#!/usr/bin/env python

from __future__ import print_function
from optparse import OptionParser
from github import Github
from os.path import expanduser
import requests
import json
from socket import setdefaulttimeout
setdefaulttimeout(120)
from os import environ
JENKINS_PREFIX="jenkins"
try:    JENKINS_PREFIX=environ['JENKINS_URL'].strip("/").split("/")[-1]
except: JENKINS_PREFIX="jenkins"
#
# Posts a message in the github issue that triggered the build
# The structure of the message depends on the option used
#

# -------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------
GH_CMSSW_ORGANIZATION = 'cms-sw'
GH_CMSSW_REPO = 'cmssw'
GH_CMSDIST_REPO = 'cmsdist'
POST_TESTS_OK = 'TESTS_OK'
POST_TESTS_FAILED = 'TESTS_FAIL'
POST_TESTING = 'TESTING'
CMSDIST_TESTS_OK_MSG = '+1\nTested compilation until {package}.\nYou can see the log here: {tests_location}'
CMSDIST_TESTS_FAIL_MSG = '-1\nBuild failed ( compiled until {package} ).\n You can see the log here: {tests_location}'
CMSDIST_COMMIT_STATUS_BASE_URL = 'https://api.github.com/repos/cms-sw/cmsdist/statuses/%s'
COMMIT_STATES_DESCRIPTION = { POST_TESTS_OK : [ 'success' , 'Tests OK' ],
                              POST_TESTS_FAILED : [ 'failure', 'Tests Failed' ],
                              POST_TESTING : [ 'pending', 'cms-bot is testing this pull request' ] }
BASE_TESTS_URL='https://cmssdt.cern.ch/SDT/%s-artifacts/cms-externals-pr-integration/{jk_build_number}/results/build.log' % JENKINS_PREFIX
BASE_TESTING_URL='https://cmssdt.cern.ch/%s/job/test-externals-prs/{jk_build_number}/' % JENKINS_PREFIX

# -------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------

#
# mars the commit with the result of the tests (success or failure)
#
def mark_commit( action, commit_hash, tests_url ):
  if opts.dryRun:
    print('Not adding status to commit %s (dry-run):\n %s' % ( commit_hash, action ))
    return

  url = CMSDIST_COMMIT_STATUS_BASE_URL % commit_hash
  headers = {"Authorization" : "token " + TOKEN }
  params = {}
  params[ 'state' ] = COMMIT_STATES_DESCRIPTION[ action ][ 0 ]
  params[ 'target_url' ] = tests_url
  params[ 'description' ] = COMMIT_STATES_DESCRIPTION[ action ][ 1 ]

  data = json.dumps(params)
  print('Setting status to %s ' % COMMIT_STATES_DESCRIPTION[ action ][ 0 ])
  print(url)
  r = requests.post(url, data=data, headers=headers)
  print(r.text)


#
# posts a message to the issue in github
# if dry-run is selected it doesn't post the message and just prints it
#
def post_message( issue, msg ):
  if opts.dryRun:
    print('Not posting message (dry-run):\n %s' % msg)
  else:
    print('Posting message:\n %s' % msg)
    issue.create_comment( msg )

# -------------------------------------------------------------------------------
# Start of execution
# --------------------------------------------------------------------------------

if __name__ == "__main__":
  parser = OptionParser( usage="%prog <jenkins-build-number> <pr-id> <arch> <last_commit> <message-type> <package-name> [ options ] \n "
                               "message-type = TESTS_OK | TESTS_FAIL | TESTING " )
  parser.add_option( "-n" , "--dry-run" , dest="dryRun" , action="store_true", help="Do not post on Github", default=False )
  opts, args = parser.parse_args( )

  if len( args ) != 6:
    parser.error( "Not enough arguments" )

  jenkins_build_number = int( args[ 0 ] )
  issue_id = int( args[ 1 ] )
  arch = args[ 2 ]
  commit_hash = args[ 3 ]
  action = args[ 4 ]
  package_name = args[ 5 ]

  TOKEN=open( expanduser( "~/.github-token" ) ).read( ).strip( )
  GH = Github( login_or_token=TOKEN )
  CMSDIST_REPO = GH.get_organization( GH_CMSSW_ORGANIZATION ).get_repo( GH_CMSDIST_REPO )
  issue = CMSDIST_REPO.get_issue( issue_id )

  if action == POST_TESTS_OK:
    tests_url=BASE_TESTS_URL.format( jk_build_number=jenkins_build_number ) 
    msg = CMSDIST_TESTS_OK_MSG.format( package=package_name, tests_location=tests_url )
    post_message( issue , msg )
    mark_commit( action, commit_hash, tests_url )

  elif action == POST_TESTS_FAILED:
    tests_url = BASE_TESTS_URL.format( jk_build_number=jenkins_build_number )
    msg = CMSDIST_TESTS_FAIL_MSG.format( package=package_name, tests_location=tests_url )
    post_message( issue , msg )
    mark_commit( action, commit_hash, tests_url )

  elif action == POST_TESTING:
   # This action only marks the commit as testing, does not post any message
    tests_url = BASE_TESTING_URL.format( jk_build_number=jenkins_build_number )
    mark_commit( action, commit_hash, tests_url )
  else:
    parser.error( "Message type not recognized" )
