#!/usr/bin/python
from httplib import HTTPSConnection
from os import getuid
import json
from urllib import urlencode

def format(s, **kwds): return s % kwds
class CMSWeb (object):
  def __init__ (self):
    self.URL_CMSWEB_BASE='cmsweb.cern.ch'
    self.URL_PHEDEX_BLOCKREPLICAS='/phedex/datasvc/json/prod/blockreplicas'
    self.URL_DBS_DATASETS='/dbs/prod/global/DBSReader/datasets'
    self.URL_DBS_FILES='/dbs/prod/global/DBSReader/files'
    self.URL_DBS_BLOCKS='/dbs/prod/global/DBSReader/blocks'
    self.conn = HTTPSConnection(self.URL_CMSWEB_BASE, cert_file='/tmp/x509up_u{0}'.format(getuid()),  timeout=30)
    self.cache = {'lfns':{}, 'datasets': {}, 'blocks': {}, 'new_lfns' : {}, "replicas" : {}}
    self.reply_cache = {}
    self.errors = 0

  def __del__(self): self.conn.close ()

  def get_cmsweb_data(self, url):
    if url in self.reply_cache: return self.reply_cache[url]
    msg =""
    try:
      self.conn.request('GET', url)
      msg = self.conn.getresponse()
      if msg.status!=200:
        self.errors = self.errors + 1
        print 'Result: {0} {1}: {2}'.format(msg.status, msg.reason, url)
        return False, {}
      self.reply_cache[url]=json.loads(msg.read())
      return True, self.reply_cache[url]
    except Exception, e:
      print "Error:", e, url
      self.errors = self.errors + 1
      return False, {}

  def search(self, lfn, lfn_info):
    if lfn in self.cache['lfns']: return self.cache['lfns'][lfn]
    self.cache['lfns'][lfn] = self.search_(lfn, lfn_info)
    return self.cache['lfns'][lfn]

  def search_block(self, block):
    if not block in self.cache["replicas"]: self.cache["replicas"][block]={}
    if not block in self.cache['blocks']:
      status, jmsg = self.get_cmsweb_data('{0}?{1}'.format(self.URL_PHEDEX_BLOCKREPLICAS, urlencode({'block': block})))
      if not status: return False
      if len(jmsg['phedex']['block']) == 0: return False
      block_data = {'at_cern' : 'no'}
      for replica in jmsg['phedex']['block'][0]['replica']:
        self.cache["replicas"][block][replica['node']]=1
        if replica['node'] != 'T2_CH_CERN': continue
        block_data['at_cern'] = 'yes'
        block_data['ds_files'] = str(replica['files'])
        block_data['ds_owner'] = replica['group'].strip().replace(" ","_")
        break
      self.cache['blocks'][block]={}
      for x in block_data: self.cache['blocks'][block][x]=block_data[x]
    return True

  def search_dataset(self, dataset):
    if not dataset in self.cache['datasets']:
      status, jmsg = self.get_cmsweb_data('{0}?{1}'.format(self.URL_DBS_DATASETS, urlencode({'detail': 1, 'dataset_access_type': '*', 'dataset': dataset})))
      if not status: return False
      self.cache['datasets'][dataset] = jmsg[0]['dataset_access_type'].strip().replace(" ","_")
    return True

  def search_lfn(self, lfn):
    status, jmsg = self.get_cmsweb_data('{0}?{1}'.format(self.URL_DBS_BLOCKS, urlencode({'detail': 1,'logical_file_name': lfn})))
    if not status: return {}
    return jmsg

  def search_(self, lfn, lfn_info):
    #print "CUR:",lfn_info
    lfn_data = {}
    for x in ["ds_status", "ds_block", "ds_owner", "at_cern", "dataset"]:
      if (not x in lfn_info) or (lfn_info[x]==""): lfn_data[x]="UNKNOWN"
    if (not "ds_files" in lfn_info) or (lfn_info["ds_files"]==""): lfn_data["ds_files"]="0"
    # Find the block
    if not 'ds_block' in lfn_info or lfn_info['ds_block']=='UNKNOWN':
      self.cache['new_lfns'][lfn]=1
      jmsg = self.search_lfn(lfn)
      if not jmsg: return lfn_data
      lfn_data['ds_block'] = jmsg[0]['block_name']
      lfn_data['dataset']  = jmsg[0]['dataset']
    else:
      lfn_data['ds_block'] = lfn_info['ds_block']
      lfn_data['dataset']  = lfn_info['dataset']

    block = lfn_data['ds_block']
    dataset = lfn_data['dataset']
    # Check if dataset is still VALID
    if not self.search_dataset(dataset): return lfn_data
    lfn_data['ds_status'] = self.cache['datasets'][dataset]

    # Check if dataset/block exists at T2_CH_CERN and belongs to IB RelVals group
    if not self.search_block(block): return lfn_data
    for x in self.cache['blocks'][block]: lfn_data[x] = self.cache['blocks'][block][x]
    return lfn_data

if __name__ == "__main__":
  from optparse import OptionParser  
  parser = OptionParser(usage="%prog <input>")
  opts, args = parser.parse_args()
  
  cmsweb = None
  for data in args:
    if not cmsweb: cmsweb=CMSWeb()
    if data.endswith(".root"):
      cmsweb.search(data,{})
    else:
      cmsweb.search_dataset(data.split("#")[0])
      cmsweb.search_block(data)
    info = {data : cmsweb.reply_cache}
    print json.dumps(info, indent=2, sort_keys=True, separators=(',',': '))
    cmsweb.reply_cache = {}

