#!/bin/python
import sys,urllib2 , json
from datetime import datetime
#Function to store data in elasticsearch
def send_payload(index,document,id,payload,passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  try:
    passw=open(passwd_file,'r').read().strip()
  except Exception as e:
    print "Couldn't read the secrets file" , str(e)

  url = "http://%s/%s/%s/" % ('cmses-master01.cern.ch:9200',index,document)
  if id: url = url+id
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'elasticsearch', passw)
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,payload)
  except Exception as e:
    print "Couldn't send data to elastic search" , str(e)
    print "Data:",payload
    return False
  return True

def get_payload(url,query):
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'kibana', 'kibana')
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,query)
    return content.read()
  except Exception as e:
    print "Couldn't send data to elastic search" , str(e)
    return ""
