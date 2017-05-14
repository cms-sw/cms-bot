#!/usr/bin/env python
import sys,urllib2 , json
from datetime import datetime
#Function to store data in elasticsearch

def resend_payload(hit, passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  return send_payload(hit["_index"], hit["_type"], hit["_id"],json.dumps(hit["_source"]),passwd_file)

def send_payload_new(index,document,id,payload,es_server,passwd_file="/data/secrets/cmssdt-es-secret"):
  index = 'cmssdt-' + index
  try:
    passw=open(passwd_file,'r').read().strip()
  except Exception as e:
    print "Couldn't read the secrets file" , str(e)

  url = "https://%s/%s/%s/" % (es_server,index,document)
  if id: url = url+id
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'cmssdt', passw)
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,payload)
  except Exception as e:
    print "Couldn't send data to elastic search" , str(e)
    return False
  return True

def send_payload_old(index,document,id,payload,passwd_file="/data/secrets/github_hook_secret_cmsbot"):
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
    return False
  return True

def send_payload(index,document,id,payload,passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  #send_payload_new(index,document,id,payload,'es-cmssdt.cern.ch:9203')
  send_payload_new(index,document,id,payload,'es-cmssdt5.cern.ch:9203')
  return send_payload_old(index,document,id,payload,passwd_file) 

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
