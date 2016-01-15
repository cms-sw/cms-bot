#!/bin/python
import sys,urllib2 , json
from datetime import datetime
#Function to store data in elasticsearch
def send_payload(index,document,id,payload):
  try:
    passw=open('/data/secrets/github_hook_secret','r').read().strip()
  except:
    print "Couldn't read the secrets file"
  
  url="https://%s/%s/%s/%s" % ('128.142.136.155',index,document,id)
  print url
  #send the data to elasticsearch
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'elasticsearch', passw)
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,payload)
  except:
    print "Couldn't send data to elastic search"

  print "Data sent to elasticsearch", content.info()
