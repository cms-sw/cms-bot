#! /usr/bin/env python

from optparse import OptionParser
from os import listdir
import re

#-----------------------------------------------------------------------------------
# This script analyses the results from the FWlite comparison ( JR Comparison )
# Per each workflow, it checks how many diffs where found. This is the number of 
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
#---- Parser Options
#-----------------------------------------------------------------------------------

parser = OptionParser(usage="usage: %prog DIR \n DIR: The directory where the results of the FWLite comparison are")

(options, args) = parser.parse_args()

#-----------------------------------------------------------------------------------
#---- Review of arguments
#-----------------------------------------------------------------------------------

if ( len(args) < 2 ):

  print 'not enough arguments\n'
  parser.print_help()
  exit()

#-----------------------------------------------------------------------------------
#---- Global Variables
#-----------------------------------------------------------------------------------

RESULTS_DIR = args[0]
WF_REGEXP = '[0-9]*p[0-9]*'
BASE_WF_MOD_PARAM = 'MOD'
BASE_WF_NUM_PARAM = 'FOR_WF'
PARAMS_FILE = args[1]

#-----------------------------------------------------------------------------------
#---- Start of execution
#-----------------------------------------------------------------------------------
f = open( PARAMS_FILE , 'w')

for current_dir in [ dir for dir in listdir( RESULTS_DIR ) if dir.startswith( 'all_Old' ) ]:
  
  print 'Processing: %s' % current_dir

  current_wf = re.search( WF_REGEXP , current_dir ).group( 0 ).replace( 'p' , '.' )
  print 'Workflow number is: %s' % current_wf

  num_diffs = len( [ file_name for file_name in listdir( RESULTS_DIR + '/' + current_dir ) if '.png' in file_name ] )
  print 'It had %s diffs' % num_diffs

  if num_diffs < 10:
    print 'This needs to be run with mod 0'
    mod = 0
  elif num_diffs < 100:
    print 'This needs to be run with mod 3'
    mod = 3
  else:
    print 'This needs to me run with mod 2'
    mod = 2

  line = BASE_WF_NUM_PARAM + '=' + current_wf + ';' + BASE_WF_MOD_PARAM + '=%s' % mod + '\n'

  f.write( line )

f.close()
 




