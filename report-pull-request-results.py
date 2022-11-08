#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function
from io import open
from os.path import expanduser, dirname, join, exists, abspath
from optparse import OptionParser
from _py2with3compatibility import run_cmd
import re
import json
import os, sys
from socket import setdefaulttimeout
from github_utils import api_rate_limits
setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(sys.argv[0]))
#-----------------------------------------------------------------------------------
#---- Parser Options
#-----------------------------------------------------------------------------------
parser = OptionParser(usage="usage: %prog ACTION [options] \n ACTION = PARSE_UNIT_TESTS_FAIL | PARSE_BUILD_FAIL "
                            "| PARSE_MATRIX_FAIL | COMPARISON_READY | GET_BASE_MESSAGE | PARSE_EXTERNAL_BUILD_FAIL "
                            "| PARSE_ADDON_FAIL | PARSE_CLANG_BUILD_FAIL | MATERIAL_BUDGET | PYTHON3_FAIL | MERGE_COMMITS")

parser.add_option("-f", "--unit-tests-file", action="store", type="string", dest="unit_tests_file", help="results file to analyse", default='None')
parser.add_option("--f2", action="store", type="string", dest="results_file2", help="second results file to analyse" )
parser.add_option("--missing_map", action="store", type="string", dest="missing_map", help="Missing workflow map file", default='None' )
parser.add_option("--recent-merges", action="store", type="string", dest="recent_merges_file", help="file with the recent merges after doing the git cms-merge-topic")
parser.add_option("--no-post", action="store_true", dest="no_post_mesage", help="I will only show the message I would post, but I will not post it in github")
parser.add_option("--repo", action="store", dest="custom_repo", help="Tells me to use a custom repository from the user cms-sw", default="cms-sw/cmssw" )
parser.add_option("--report-file", action="store", type="string", dest="report_file", help="Report the github comment in report file instead of github", default='')
parser.add_option("--report-url", action="store", type="string", dest="report_url", help="URL where pr results are stored.", default='')
parser.add_option("--commit", action="store", type="string", dest="commit", help="Pull request latest commit", default='')

(options, args) = parser.parse_args()

def openlog(log, mode='r'):
  return open(log, mode=mode, encoding='utf-8', errors='ignore')

def writelog(ref, line):
  ref.write(line.encode('ascii', 'ignore').decode('utf-8') if sys.version_info[0] < 3 else line)
#
# Reads the log file for a step in a workflow and identifies the error if it starts with 'Begin Fatal Exception'
#
def get_wf_error_msg(out_file, filename=True):
  if out_file.endswith(MATRIX_WORKFLOW_STEP_LOG_FILE_NOT_FOUND):
    return ''
  error_lines = ''
  if exists( out_file ):
    reading = False
    for line in openlog( out_file):
      if reading:
        error_lines += line
        if '----- End Fatal Exception' in line:
          reading = False
          break
      elif '----- Begin Fatal Exception' in line:
        error_lines += '\n'+ line
        reading = True
  if not error_lines and filename:
    error_lines = "/".join(out_file.split("/")[-2:])+'\n'
  return error_lines

#
# Reads a line that starts with 'ERROR executing',  the line has ben splitted by ' '
# it gets the directory where the results for the workflow are, the step that failed
# and the log file
#
def parse_workflow_info( parts, relval_dir ):
  workflow_info = {}
  # this is the output file to which the output of command for the step was directed
  # it starts asumed as not found
  out_file = MATRIX_WORKFLOW_STEP_LOG_FILE_NOT_FOUND
  workflow_info[ 'step' ] = MATRIX_WORKFLOW_STEP_NA
  out_directory = "UNKNOWN"
  for i in range( 0 , len( parts ) ):
    current_part = parts[ i ]
    if ( current_part == 'cd' ):
      out_directory = parts[ i+1 ] 
      out_directory = re.sub( ';' , '', out_directory)
      number = re.sub( '_.*$' , '' , out_directory )
      workflow_info[ 'out_directory' ] = out_directory
      workflow_info[ 'number' ] = number
    if ( current_part == '>' ):
      out_file = parts[ i+1 ]
      step = re.sub( '_.*log' , '' , out_file)
      workflow_info[ 'out_file'] = out_file
      workflow_info[ 'step' ] = step

  workflow_info['message'] = get_wf_error_msg(join(relval_dir, out_directory, out_file))
  return workflow_info
    
#
# Reads the log file for the matrix tests. It identifyes which workflows failed
# and then proceeds to read the corresponding log file to identify the message
#
def read_matrix_log_file(matrix_log):
  workflows_with_error = [ ]
  relval_dir = join(dirname (matrix_log), "runTheMatrix-results")
  common_errors = []
  for line in openlog( matrix_log):
    line = line.strip()
    if 'ERROR executing' in line:
      print('processing: %s' % line) 
      parts = re.sub("\s+"," ",line).split(" ")
      workflow_info = parse_workflow_info( parts, relval_dir)
      if 'number' in workflow_info:
        workflows_with_error.append( workflow_info )
    elif ' Step0-DAS_ERROR ' in line:
      print('processing: %s' % line)
      parts = line.split("_",2)
      workflow_info = {}
      workflow_info[ 'step' ] = "step1"
      workflow_info[ 'number' ] = parts [0]
      workflow_info[ 'message' ] = "DAS Error"
      workflows_with_error.append( workflow_info )
    elif 'ValueError: Undefined' in line:
      common_errors.append(line+"\n")

  # check if it was timeout
  message = "\n## RelVals\n\n"
  if 'ERROR TIMEOUT' in line:
    message +=  'The relvals timed out after 4 hours.\n'
  if common_errors:
    message +=  ''.join(common_errors)
  cnt = 0
  max_show = 3
  extra_msg = False
  for wf in workflows_with_error:
    wnum = wf['number']
    cnt += 1
    if 'out_directory' in wf:
      wnum = "[%s](%s/runTheMatrix-results/%s)" % (wnum, options.report_url, wf['out_directory'])
    if cnt<=max_show:
      msg =  wf['message'].strip()
      if len(msg.split('\n'))>1:
        message += '- ' + wnum + '\n```\n' + msg + '\n```\n'
      else:
        message += '- ' + wnum + '```' + msg + '```\n'
    else:
      if not extra_msg:
        extra_msg = True
        message += '<details>\n<summary>Expand to see more relval errors ...</summary>\n\n'
      message += '- ' + wnum + '\n'
  if extra_msg: message += '</details>\n\n'
  send_message_pr(message)

#
# reads the addon tests log file and gets the tests that failed
#
def cmd_to_addon_test(command, addon_dir):
  try:
    cmdMatch = re.match("^\[(.+):(\d+)\] +(.*)", command)
    addon_subdir = cmdMatch.group(1)
    logfile = 'step%s.log' % cmdMatch.group(2)
    e, o = run_cmd('ls -d %s/%s/%s 2>/dev/null | tail -1' % (addon_dir, addon_subdir, logfile))
  except:
    commandbase = command.replace(' ','_').replace('/','_')
    logfile='%s.log' % commandbase[:150].replace("'",'').replace('"','').replace('../','')
    e, o = run_cmd("ls -d %s/*/%s 2>/dev/null | tail -1" % (addon_dir, logfile))
  if (not e) and o:
    return (o.split("/")[-2], get_wf_error_msg(o, False).strip())
  print("ERROR: %s -> %s" % (command, o))
  return ("", "")

def read_addon_log_file(unit_tests_file):
  message='\n## AddOn Tests\n\n'
  addon_dir = join(dirname(unit_tests_file), "addOnTests")
  cnt = 0
  max_show = 3
  extra_msg = False
  for line in openlog(unit_tests_file):
    line = line.strip()
    if( ': FAILED -' in line):
      cnt += 1
      tname, err = cmd_to_addon_test(line.split(': FAILED -')[0].strip(), addon_dir)
      if not tname: tname = "unknown"
      else: tname = "[%s](%s/addOnTests/%s)" % (tname, options.report_url, tname)
      if cnt <= max_show:
        if err: line = err
        message += "- "+ tname + '\n```\n' + line + '\n```\n'
      else:
        if not extra_msg:
          extra_msg = True
          message += '<details>\n<summary>Expand to see more addon errors ...</summary>\n\n'
        message += '- ' + tname + '\n'
  if extra_msg: message += '</details>\n\n'
  send_message_pr(message)

#
# reads material budget logs
#
def read_material_budget_log_file(unit_tests_file):
  message = '\n## Material Budget\n\nThere was error running material budget tests.'
  send_message_pr(message)

def get_recent_merges_message():
  message = ""
  if options.recent_merges_file:
    extra_msg = []
    json_obj = json.load(openlog(options.recent_merges_file))
    for r in json_obj:
      for pr in json_obj[r]: extra_msg.append(" - @%s %s#%s" % (json_obj[r][pr]['author'], r, pr))

    if extra_msg:
      message += '\n\nThe following merge commits were also included on top of IB + this PR '\
                 'after doing git cms-merge-topic: \n'

      for l in extra_msg: message += l + '\n'

      message += '\nYou can see more details here:\n'
      message += GITLOG_FILE_BASE_URL +'\n'
      message += GIT_CMS_MERGE_TOPIC_BASE_URL + '\n'
  return message

def get_pr_tests_info():
  message = ""
  if options.commit:
    message = "\n**COMMIT**: %s" % options.commit
  message += "\n**CMSSW**: "
  if 'CMSSW_VERSION' in os.environ:
    message +=  os.environ['CMSSW_VERSION']
  else:
    message +=  "UNKNOWN"
  if 'SCRAM_ARCH' in os.environ:
    message += '/' + os.environ['SCRAM_ARCH']
  else:
    message += '/UNKNOWN'
  if ('ENABLE_BOT_TESTS' in os.environ) and os.environ['ENABLE_BOT_TESTS']:
    message += "\n**Additional Tests**: %s" % os.environ['ENABLE_BOT_TESTS']
  return message


#
# reads the build log file looking for the first error
# it includes 5 lines before and 5 lines after the error
#
def read_build_log_file(build_log, isClang=False , toolconf=False):
  line_number = 0
  error_line = 0
  lines_to_keep_before=5
  lines_to_keep_after=5
  lines_since_error=0
  lines_before = ['']
  lines_after = ['']
  error_found = False
  for line in openlog(build_log):
    line_number += 1
    if (not error_found):
      lines_before.append(line)
      if (line_number > lines_to_keep_before):
        lines_before.pop(0)
    #this is how it determines that a line has an error
    if ('error: ' in line) or line.startswith("gmake: "):
      error_found = True
      error_line = line_number
    if error_found:
      if (lines_since_error == 0):
        lines_since_error += 1
        continue
      elif (lines_since_error <= lines_to_keep_after):
        lines_since_error += 1
        lines_after.append(line)
      else:
        break

  message = ""
  err_type = "compilation warning"
  if error_found: err_type = "compilation error"
  if isClang:
    cmd = openlog( build_log).readline()
    message += '\n## Clang Build\n\nI found '+err_type+' while trying to compile with clang. '
    message += 'Command used:\n```\n' + cmd +'\n```\n'
  elif toolconf:
    message += '\n## External Build\n\nI found '+err_type+' when building: '
  else:
    message += '\n## Build\n\nI found '+err_type+' when building: '

  if error_found:
    message += '\n\n<pre>'
    for line in lines_before:
      message += line + '\f'
    for line in lines_after:
      message += line + '\f'
    message += '</pre>'
  else:
    message += " See details on the summary page."

  send_message_pr(message)

#
# reads the unit tests file and gets the tests that failed
#
def read_unit_tests_file(unit_tests_file):
  errors_found=''
  err_cnt = 0
  for line in openlog(unit_tests_file):
    if( 'had ERRORS' in line):
      errors_found += line
      err_cnt += 1
      if err_cnt > 3:
        errors_found += "and more ...\n"
        break
  message = '\n## Unit Tests\n\nI found errors in the following unit tests:\n\n<pre>%s</pre>' % errors_found
  send_message_pr(message)


#
# reads the python3 file and gets the tests that failed
#
def read_python3_file(python3_file):
  errors_found=''
  err_cnt = 0
  for line in openlog(python3_file):
    if( ' Error compiling ' in line):
      errors_found += line
      err_cnt += 1
      if err_cnt > 3:
        errors_found += "and more ...\n"
        break
  message = '\n#Python3\n\nI found errors: \n\n <pre>%s</pre>' % errors_found
  send_message_pr(message)


#
# Sends a message to the pull request. It takes into account if the dry-run option was set
# If checkDuplicateMessage is set to true, it checks if the message was already posted in the thread
# and if it is it doesn't post it again
#
def send_message_pr(message):
  if options.no_post_mesage:
    print('Not posting message (dry-run): \n ', message)
    return
  with openlog(options.report_file, "a") as rfile:
    writelog(rfile, message+"\n")
  return


#
# sends an approval message for a pr in cmssw
#
def add_to_report(message):
  if not message: return
  with openlog(options.report_file, "a") as rfile:
    writelog(rfile, message+"\n")
  return

def get_base_message():
  add_to_report(get_pr_tests_info())
  return

def send_comparison_ready_message(comparison_errors_file, wfs_with_das_inconsistency_file, missing_map ):
  message = '\n## Comparison Summary\n\n'
  wfs_with_errors = ''
  for line in openlog( comparison_errors_file ):
    line = line.rstrip()
    parts = line.split( ';' )
    wf = parts[ 0 ]
    step = parts[ 1 ]
    wfs_with_errors += ( wf + ' step ' + step + '\n' )

  if wfs_with_errors != '':
    error_info = COMPARISON_INCOMPLETE_MSG.format( workflows=wfs_with_errors )
    message += '\n\n' + error_info

  wfs_das_inconsistency = openlog( wfs_with_das_inconsistency_file).readline().rstrip().rstrip(',').split( ',' )

  if '' in wfs_das_inconsistency:
    wfs_das_inconsistency.remove( '' )

  if wfs_das_inconsistency:
    das_inconsistency_info = DAS_INCONSISTENCY_MSG.format( workflows=', '.join( wfs_das_inconsistency ) )
    message += '\n\n' + das_inconsistency_info

  if missing_map and exists (missing_map):
    missing = []
    for line in openlog(missing_map):
      line = line.strip()
      if line: missing.append("   * "+line)
    if missing:
      from categories import COMPARISON_MISSING_MAP
      map_notify = ", ".join([ "@"+u for u in COMPARISON_MISSING_MAP] )
      message += "\n\n"+map_notify+" comparisons for the following workflows were not done due to missing matrix map:\n"+"\n".join(missing)

  alt_comp_dir = join(dirname(comparison_errors_file), "upload","alternative-comparisons")
  print("Alt comparison directory: ",alt_comp_dir)
  if exists(alt_comp_dir):
    err, out = run_cmd("grep ' Compilation failed' %s/runDQMComp-*.log" % alt_comp_dir)
    print(out)
    if not err:
      err_wfs = {}
      for line in out.split("\n"):
        wf = line.split(".log:",1)[0].split("runDQMComp-")[-1]
        err_wfs [wf]=1
      if err_wfs: message += "\n\nAlternative comparison was/were failed for workflow(s):\n"+"\n".join(list(err_wfs.keys()))

  JRCompSummaryLog = join(dirname(comparison_errors_file), "upload/validateJR/qaResultsSummary.log")
  print("JR comparison Summary: ",JRCompSummaryLog)
  if exists(JRCompSummaryLog):
    err, out = run_cmd("cat %s" % JRCompSummaryLog)
    if (not err) and out:
      message += "\n\n**Summary**:\n"
      for l in out.split("\n"):
        if l.strip(): message += " - %s\n" % l.strip()

  send_message_pr(message )

def complain_missing_param(param_name):
  print('\n')
  print('I need a %s to continue' % param_name)
  print('\n')
  parser.print_help()
  exit()

#----------------------------------------------------------------------------------------
#---- Global variables
#---------------------------------------------------------------------------------------

COMPARISON_INCOMPLETE_MSG = 'There are some workflows for which there are errors in the baseline:\n {workflows} ' \
                            'The results for the comparisons for these workflows could be incomplete \n' \
                            'This means most likely that the IB is having errors in the relvals.'\
                            'The error does NOT come from this pull request'
DAS_INCONSISTENCY_MSG = 'The workflows {workflows} have different files in step1_dasquery.log than the ones ' \
                        'found in the baseline. You may want to check and retrigger the tests if necessary. ' \
                        'You can check it in the "files" directory in the results of the comparisons'

MATRIX_WORKFLOW_STEP_LOG_FILE_NOT_FOUND = 'Not Found'
MATRIX_WORKFLOW_STEP_NA = 'N/A'

#----------------------------------------------------------------------------------------
#---- Check arguments and options
#---------------------------------------------------------------------------------------

if (len(args)==0):
  print('you have to choose an action')
  parser.print_help()
  exit()

ACTION = args[0]

if (ACTION == 'prBot.py'):
  print('you have to choose an action')
  parser.print_help()
  exit()

print('you chose the action %s' % ACTION)

if (options.report_url=='') or (options.report_file==''):
  complain_missing_param( 'report url/report file' )
  exit()

GITLOG_FILE_BASE_URL='%s/git-recent-commits.json' % options.report_url
GIT_CMS_MERGE_TOPIC_BASE_URL='%s/git-merge-result' % options.report_url

if ( ACTION == 'GET_BASE_MESSAGE' ):
  get_base_message()
elif ( ACTION == 'PARSE_UNIT_TESTS_FAIL' ):
  read_unit_tests_file(options.unit_tests_file)
elif ( ACTION == 'PARSE_EXTERNAL_BUILD_FAIL' ):
  read_build_log_file(options.unit_tests_file, toolconf=True )
elif ( ACTION == 'PARSE_BUILD_FAIL' ):
  read_build_log_file(options.unit_tests_file)
elif ( ACTION == 'PARSE_MATRIX_FAIL' ):
  read_matrix_log_file(options.unit_tests_file )
elif ( ACTION == 'PARSE_ADDON_FAIL' ):
  read_addon_log_file(options.unit_tests_file )
elif ( ACTION == 'COMPARISON_READY' ):
  send_comparison_ready_message(options.unit_tests_file, options.results_file2, options.missing_map )
elif( ACTION == 'PARSE_CLANG_BUILD_FAIL'):
  read_build_log_file(options.unit_tests_file, isClang=True )
elif( ACTION == 'PYTHON3_FAIL'):
  read_python3_file(options.unit_tests_file )
elif( ACTION == 'MATERIAL_BUDGET'):
  read_material_budget_log_file(options.unit_tests_file)
elif ( ACTION == 'MERGE_COMMITS'):
  add_to_report(get_recent_merges_message())
else:
  print("I don't recognize that action!")
