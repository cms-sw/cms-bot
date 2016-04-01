#!/usr/bin/python
from commands import getstatusoutput
import re ,sys,time , datetime
from es_utils import send_payload
from json import dumps
payload = {}
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
match_hn = re.compile('.*\|\/.*emails')
match_tmp = re.compile('.*\|\/.*Time\(s\)')
temp_fails = []
egrps = []
for line in sys.stdin:
#  print line
  if 'Processing Initiated:' in line: timestpline = line
  elif re.match(match_tmp,line): temp_fails.append(line)
  elif 'Messages To Recipients:' in line: msgs_num = line
  elif 'Addressed Recipients:' in line : adrpts = line
  elif 'Bytes Transferred:' in line: byttr = line
  elif re.match(match_hn,line): egrps.append(line)
  else:
    pass
#process info
timestamp = time.mktime(datetime.datetime.strptime(str(timestpline[30:]).strip(),'%a %b %d %H:%M:%S %Y').timetuple())
temp_fails = dict(map(map_int_val,(dict([map(cust_strip,x.split(' ')[-3:-1]) for x in temp_fails])).items()))
msgs_num= map(str.strip,msgs_num.split(':'))
adrpts = map(str.strip, adrpts.split(':'))
byttr = map(str.strip, byttr.split(':'))
egrp_emails = dict(map(rm_extra,[x.strip() for x in egrps]))
#send info
payload['@timestamp'] = timestamp
payload['msgs_to_rcpts'] = msgs_num[1]
payload['addressed_rcpts'] = adrpts[1]
payload['byts_transfd'] = byttr[1]
total=0
for k in egrp_emails:
  payload['hn-'+k] = egrp_emails[k]
  total += egrp_emails[k]
payload['hn_emails_total'] = total
for k in temp_fails:
  payload['temp_failures-'+k] = temp_fails[k]
print payload
send_payload("hypernews","mailinfo", id="", dumps(payload), passwd_file="/data/es/es_secret")
