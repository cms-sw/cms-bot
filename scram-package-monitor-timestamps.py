#!/usr/bin/env python
import os, errno
from optparse import OptionParser
from os.path import join
from time import strftime

TERM_CMD = "kill_reader"

def create_dir(dir_to_create):
  try:
    os.makedirs(dir_to_create)
  except OSError as exception:
    if exception.errno != errno.EEXIST:
      raise exception

if __name__ == "__main__":
  WORKSPACE = os.getenv("WORKSPACE", "./")
  WORK_DIR = join(WORKSPACE, "pkg_mon")

  parser = OptionParser(usage="%prog <-s|-e> -p <package>")
  parser.add_option("-s", "--start", dest="start", action="store_true",
                    help="Building started for package", default=True)
  parser.add_option("-e", "--stop", dest="start", action="store_false",
                    help="Building done for package", default=True)
  parser.add_option("-p", "--package", dest="pkg_name",
                    help="Package name to track", default=None)
  opts, args = parser.parse_args()
  
  pkg_name = opts.pkg_name
  create_dir(WORK_DIR)

  # Create the file for the current invocation.
  if pkg_name:
    prefix = opts.start and strftime("start_%s-") or strftime("stop_%s-")
    filename = prefix + pkg_name.replace("/",":")
    while(True):
      try:
        open(join(WORK_DIR, filename), "a").close()
        break
      except:
        create_dir(WORK_DIR)
  elif not opts.start:
    while(True):
      try:
        open(join(WORK_DIR, TERM_CMD), "a").close()
        break
      except:
        create_dir(WORK_DIR)
