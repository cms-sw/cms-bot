#!/usr/bin/python
from commands import getstatusoutput
import time
from es_utils import send_payload
from json import dumps

logFile = '/tmp/logwatch'
payload = {}
payload['@timestamp'] = time.time()

def cust_strip(str_in):
  return str_in.lstrip('/').rstrip(':"')

def prs_tprl(str_in):
  str_out = map(str.strip,str_in.split(':'))
  val = int(str_out[0].split('/')[0])
  key = str_out[1].split(' ')[0]
  return key,val

def rm_extra(str_in):
  str_out = str_in.split(' ')
  return str_out[-4].lstrip('/').rstrip('"'),int(str_out[-2])

def map_int_val(pair):
  key , val = pair
  return key , int(val)

#get relevant info
err, temp_fails = getstatusoutput("grep '|/.*Time(s)' " + logFile)
err, msgs_num = getstatusoutput("grep 'Messages To Recipients:' " + logFile)
err, adrpts = getstatusoutput("grep 'Addressed Recipients:' " + logFile)
err , byttr = getstatusoutput("grep 'Bytes Transferred:' " +logFile)
err , top_rlys = getstatusoutput("grep '^[[:space:]]*[0-9]*\/[0-9]*:' " + logFile)
err , egrps = getstatusoutput("grep '|/.*emails' " + logFile)
#process info
temp_fails = dict(map(map_int_val,(dict([map(cust_strip,x.split(' ')[-3:-1]) for x in temp_fails.split('\n')])).items()))
msgs_num= map(str.strip,msgs_num.split(':'))
adrpts = map(str.strip, adrpts.split(':'))
byttr = map(str.strip, byttr.split(':'))
top_relays =  dict(map(prs_tprl,map(str.strip,top_rlys.split('\n'))))
egrp_emails = dict(map(rm_extra,[x.strip() for x in egrps.split('\n')]))
#send info
payload['msgs_to_rcpts'] = msgs_num[1]
payload['addressed_rcpts'] = adrpts[1]
payload['byts_transfd'] = byttr[1]
payload['top_relys'] = top_relays
payload['egroups'] = egrp_emails
payload['temp_failures'] = temp_fails
print payload
send_payload("hypernews","mailinfo", dumps(payload), passwd_file="/data/es/es_secret")
