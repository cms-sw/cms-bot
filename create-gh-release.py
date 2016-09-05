#!/usr/bin/env python
import urllib2, sys, json
from os.path import expanduser
from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO

GH_TOKEN = open( expanduser("~/.github-token")).read().strip()
release_name = sys.argv[1]
branch =  sys.argv[2]
print 'Creating release:\n %s based on %s' % (release_name, branch)

# creating releases will be available in the next version of pyGithub
params = { "tag_name" : release_name, 
         "target_commitish" : branch,
         "name" : release_name,
         "body" : 'cms-bot is going to build this release',
         "draft" : False, 
         "prerelease" : False }

request = urllib2.Request("https://api.github.com/repos/" + GH_CMSSW_ORGANIZATION + "/" + GH_CMSSW_REPO +"/releases",
                          headers={"Authorization" : "token " + GH_TOKEN })
request.get_method = lambda: 'POST'
print '--'
try:
  print urllib2.urlopen( request, json.dumps( params  ) ).read()
  print "OK release",release_name,"created"
except Exception as e:
  print 'There was an error while creating the release:\n', e

