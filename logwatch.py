#!/usr/bin/env python
from os.path import exists, join, basename
from sys import exit
from commands import getstatusoutput

def run_cmd (cmd, exit_on_error=True):
  err, out = getstatusoutput (cmd)
  if err and exit_on_error:
    print out
    exit (1)
  return out

class logwatch (object):
  def __init__ (self, service, log_dir="/var/log"):
    self.log_dir = join(log_dir,"logwatch_" + service)

  def _add_cmd (self, service_log, info_file, line_num=1, keep_file=True):
    precmd = "cat %s" % service_log
    if line_num>1: precmd = "tail -n +%s %s" % (str(line_num), service_log)
    postcmd = "head -1 %s > %s && wc -l %s  | sed 's| .*||' >> %s" % (service_log, info_file,service_log, info_file)
    if not keep_file: postcmd = postcmd + " && rm -f %s" % service_log
    return (precmd,postcmd)

  def get_command(self, logs):
    log_dir   = self.log_dir
    info_file = join(log_dir, "info")
    run_cmd ("mkdir -p %s/logs" % log_dir)
    first_file = True
    line_num = 0
    first_line = ""
    all_cmds = []
    if exists(info_file):
      items = run_cmd("head -2 %s" % info_file).split("\n",1)
      first_line = items[0]
      line_num = int(items[1])
    for log in reversed(logs):
      service_log = join (log_dir, "logs", basename(log))
      run_cmd ("rsync -a %s %s" % (log, service_log))
      log_line = "XXX"
      if line_num>0:
        log_line = run_cmd("head -1 %s" % service_log)
      matched = False
      if log_line != first_line:
        all_cmds.insert(0,self._add_cmd(service_log, info_file, line_num=1, keep_file=first_file))
      else:
        all_cmds.insert(0,self._add_cmd(service_log, info_file, line_num, keep_file=first_file))
        matched = True
      if first_file: first_file = False
      if matched: break
    return all_cmds

