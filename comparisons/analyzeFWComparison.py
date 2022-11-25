#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from optparse import OptionParser
from os import walk
import re

#-----------------------------------------------------------------------------------
# This script analyses the results from the FWlite comparison ( JR Comparison )
# Per each workflow, it checks how many diffs were found. This is the number of 
# png files that are present.
# 
# -If the workflow has less than 10 differences, the DQM comparison should be run 
#  with mod 0
# -If the workflow has from 10 to 100 differences, the DQM comparison should be run
#  with mod 3
# -Else run with mod 2
#
# The results will be saved in the file DQMParameters.txt which indicates to the 
# next step in the comparison, how it should be run. 
#

#-----------------------------------------------------------------------------------
#---- Start of execution
#-----------------------------------------------------------------------------------

if __name__ == "__main__":

  #-----------------------------------------------------------------------------------
  #---- Parser Options
  #-----------------------------------------------------------------------------------
  parser = OptionParser(usage="usage: %prog DIR OUTFILE \n DIR: The directory where the results of the FWLite comparison are"
                                                       "\n OUTFILE: The file to which you want to save the parameters")

  parser.add_option( "-R" , "--relmon" , dest="relmon" , action="store_true", help="Generate the thresholds for the relmon comparisons", default=False )
  (options, args) = parser.parse_args()

  #-----------------------------------------------------------------------------------
  #---- Review of arguments
  #-----------------------------------------------------------------------------------

  if ( len(args) < 2 ):

    print('not enough arguments\n')
    parser.print_help()
    exit()

  #-----------------------------------------------------------------------------------
  #---- Global Variables
  #-----------------------------------------------------------------------------------

  RESULTS_DIR = args[0]
  WF_REGEXP = '[0-9]{1,}p[0-9]{1,}'
  BASE_WF_NUM_PARAM = 'FOR_WF'
  PARAMS_FILE = args[1]
  ALT_COMP_PARAMS = { 0:'MOD=0', 2:'MOD=2', 3:'MOD=3' }
  RELMON_COMP_THRESHOLDS = { 0:'TH=0.999999999999', 2:'TH=0.1', 3:'TH=0.999' }

  params_dict = RELMON_COMP_THRESHOLDS if options.relmon else ALT_COMP_PARAMS
  worflow_params = {}

  for iwalk,(current_dir,subdir,files) in enumerate(walk( RESULTS_DIR )):
    #naming convention is that a comparison sub-directory starts with 'all_'
    if not current_dir.split('/')[-1].startswith('all_'): continue
    if not '_' in current_dir: continue
    current_wf = current_dir.split('_',)[0]
    print('Processing: %s' % current_dir)
    if '/' in current_wf: current_wf=current_wf.split('/')[-1]
    if not current_wf[0].isdigit(): continue
   
    print('Workflow number is: %s' % current_wf)
    diff_files = [file for file in files if file.endswith('.png')]
    num_diffs = len( diff_files )
    print('It had %s diffs' % num_diffs)

    if num_diffs < 10:
      mod = 0
    elif num_diffs < 100:
      mod = 3
    else:
      mod = 2

    print('This needs to be run with %s' % params_dict [ mod ])
    if current_wf in worflow_params:
      #print('taking max of',mod,'and',worflow_params[current_wf])
      worflow_params[current_wf] = max(mod,worflow_params[current_wf])
    else:
      worflow_params[current_wf] = mod

  f = open( PARAMS_FILE , 'w')
  for wf,mod in worflow_params.items():
    f.write( '%s=%s;%s\n'%(BASE_WF_NUM_PARAM,wf,RELMON_COMP_THRESHOLDS[mod]) )
  f.close()
 




