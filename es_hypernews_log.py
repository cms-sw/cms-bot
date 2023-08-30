#!/usr/bin/env python3
from _py2with3compatibility import run_cmd
import re, sys, datetime
from es_utils import send_payload
from json import dumps


def cust_strip(str_in):
  return str_in.lstrip('/').rstrip(':"')


def prs_tprl(str_in):
  str_out = list(map(str.strip,str_in.split(':')))
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
payload = {}
err , cmd_out = run_cmd('logwatch --range yesterday --detail 10 --service sendmail')
if err:
  sys.exit(1)
for line in cmd_out.split('\n'):
  if re.match(match_tmp,line): temp_fails.append(line)
  elif 'Messages To Recipients:' in line: msgs_num = line
  elif 'Addressed Recipients:' in line : adrpts = line
  elif 'Bytes Transferred:' in line: byttr = line
  elif re.match(match_hn,line): egrps.append(line)

#process info
yesterday = datetime.date.today() - datetime.timedelta(1)
timestp = int(yesterday.strftime("%s")) * 1000
temp_fails = dict(list(map(map_int_val,list((dict([list(map(cust_strip,x.split(' ')[-3:-1])) for x in temp_fails])).items()))))
msgs_num= list(map(str.strip,msgs_num.split(':')))
adrpts = list(map(str.strip, adrpts.split(':')))
byttr = list(map(str.strip, byttr.split(':')))
egrp_emails = dict(list(map(rm_extra,[x.strip() for x in egrps])))
#send info
payload['@timestamp'] = timestp
payload['msgs_to_rcpts'] = msgs_num[1]
payload['addressed_rcpts'] = adrpts[1]
payload['byts_transfd'] = byttr[1]
total=0
for k in egrp_emails:
  payload['hn-'+k] = egrp_emails[k]
  total += egrp_emails[k]
payload['posts'] = total
payload['forums'] = len(egrp_emails)
for k in temp_fails:
  payload['fail-'+k] = temp_fails[k]
send_payload("hypernews","mailinfo",timestp, dumps(payload))
