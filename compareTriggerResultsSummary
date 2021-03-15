#!/usr/bin/env python
"""
Script to summarise the outputs of compareTriggerResults
(i.e. the outputs of hltDiff in .json format)
"""
from __future__ import print_function
import argparse
import os
import json
import glob

def KILL(message):
  raise RuntimeError(message)

def WARNING(message):
  print('>> Warning -- '+message)

def compareTriggerResultsSummary(**kwargs):
  inputDir = kwargs.get('inputDir')
  filePattern = kwargs.get('filePattern')
  summaryFilePath = kwargs.get('outputFile')
  summaryFormat = kwargs.get('outputFormat')
  dryRun = kwargs.get('dryRun', False)
  verbosity = kwargs.get('verbosity', 0)

  inputFiles = glob.glob(os.path.join(inputDir, filePattern))

  wfDict = {}
  for inpf in sorted(inputFiles):
    fBasename, wfName = os.path.basename(inpf), os.path.dirname(os.path.relpath(inpf, inputDir))
    numEventsTotal, numEventsWithDiffs = None, None
    try:
      jsonDict = json.load(open(inpf, 'r'))
      numEventsTotal = int(jsonDict["configuration"]["events"])
      numEventsWithDiffs = len(jsonDict["events"])
    except:
      if verbosity > 10:
        WARNING('compareTriggerResultsSummary -- failed to extract hltDiff statistics from input file: '+inpf)

    if numEventsTotal is None or numEventsWithDiffs is None: continue

    # fill dictionary
    procName = os.path.splitext(fBasename)[0]
    if wfName not in wfDict: wfDict[wfName] = {}

    if procName in wfDict[wfName]:
      if verbosity > 10:
        warn_msg = 'process key "'+procName+'" already exists for workflow "'+wfName+'" (will be ignored)'
        WARNING('compareTriggerResultsSummary -- '+warn_msg+': '+inpf)
      continue

    wfDict[wfName][procName] = {'numEventsTotal': numEventsTotal, 'numEventsWithDiffs': numEventsWithDiffs}

  if not wfDict:
    if verbosity >= 0:
      WARNING('compareTriggerResultsSummary -- found zero inputs to be compared (no outputs produced)')
    return -1

  # hltDiff calls
  numWorkflowsChecked, numWorkflowsWithDiffs = 0, 0
  summaryLines = []

  if summaryFormat == 'html':
    summaryLines += [
      '<html>',
      '<head><style> table { border-spacing: 18px; }</style></head>',
      '<body><h3>Summary of edm::TriggerResults Comparisons</h3><table>',
      '<tr><td>Workflow</td><td>Process Name</td><td>Events with Diffs</td><td>Events Processed</td></tr>',
    ]
  elif summaryFormat == 'txt':
    summaryLines += ['| {:25} | {:18} | {:12} | {:}'.format('Events with Diffs', 'Events Processed', 'Process Name', 'Workflow')]
    summaryLines += ['-'*100]

  try:
    sortedWfNames = sorted(wfDict, key=lambda k: float(k.split('_')[0]))
  except:
    sortedWfNames = sorted(wfDict.keys())

  for wfName in sortedWfNames:
    wfNameShort = wfName.split('_')[0]

    wfHasDiff = False
    for procName in sorted(wfDict[wfName]):
      numEventsTotal = wfDict[wfName][procName]['numEventsTotal']
      numEventsWithDiffs = wfDict[wfName][procName]['numEventsWithDiffs']

      wfHasDiff |= (numEventsWithDiffs > 0)

      if summaryFormat == 'html':
        summaryLines += [
          '<tr>',
          '  <td align="left"><a href="'+wfName+'">'+wfNameShort+'</a></td>',
          '  <td align="center"><a href="'+os.path.join(wfName, procName+'.log')+'">'+procName+'</a></td>',
          '  <td align="right">'+str(numEventsWithDiffs)+'</td>',
          '  <td align="right">'+str(numEventsTotal)+'</td>',
          '</tr>',
        ]
      elif summaryFormat == 'txt':
        summaryLines += ['| {:25d} | {:18d} | {:12} | {:}'.format(numEventsWithDiffs, numEventsTotal, procName, wfName)]

    numWorkflowsChecked += 1
    if wfHasDiff: numWorkflowsWithDiffs += 1

    if summaryFormat == 'txt':
      summaryLines += ['-'*100]

  if summaryFormat == 'html':
    summaryLines += ['</table></body></html>']

  if dryRun: return 0

  if summaryLines:
    if os.path.exists(summaryFilePath):
      if verbosity > 0:
        WARNING('compareTriggerResultsSummary -- target output file already exists (summary will not be produced)')
    else:
      with open(summaryFilePath, 'w') as summaryFile:
        for _tmp in summaryLines: summaryFile.write(_tmp+'\n')

  if verbosity >= 0:
    if numWorkflowsChecked == 0:
      print('SUMMARY TriggerResults: no workflows checked')
    elif numWorkflowsWithDiffs == 0:
      print('SUMMARY TriggerResults: no differences found')
    else:
      print('SUMMARY TriggerResults: found differences in {:d} / {:d} workflows'.format(numWorkflowsWithDiffs, len(wfDict.keys())))

  return numWorkflowsWithDiffs

#### main
if __name__ == '__main__':
    ### args
    parser = argparse.ArgumentParser(prog='./'+os.path.basename(__file__), formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)

    parser.add_argument('-i', '--input-dir', dest='input_dir', action='store', default=None, required=True,
                        help='path to input directory')

    parser.add_argument('-f', '--file-pattern', dest='file_pattern', action='store', default='*.json',
                        help='pattern to select files in the input directory (default: "*.json")')

    parser.add_argument('-o', '--output-file', dest='output_file', action='store', default=None, required=True,
                        help='path to output file (summary of comparisons)')

    parser.add_argument('-F', '--output-format', dest='output_format', action='store', default='txt', choices=["html", "txt"],
                        help='format of output file (must be "txt" or "html") (default: "txt")')

    parser.add_argument('-d', '--dry-run', dest='dry_run', action='store_true', default=False,
                        help='enable dry-run mode (default: False)')

    parser.add_argument('-v', '--verbosity', dest='verbosity', type=int, default=0,
                        help='level of verbosity (default: 0)')

    opts, opts_unknown = parser.parse_known_args()
    ### -------------------------

    # check: unrecognized command-line arguments
    if len(opts_unknown) > 0:
      KILL('unrecognized command-line arguments: '+str(opts_unknown))

    # check: input directories
    if not os.path.isdir(opts.input_dir):
      KILL('invalid path to input directory [-i]: '+opts.input_dir)

    # check: output
    outFile = opts.output_file
    if not opts.dry_run and os.path.exists(outFile):
      KILL('target output file already exists [-o]: '+outFile)

    # analyse inputs and produce summary
    compareTriggerResultsSummary(**{
      'inputDir': opts.input_dir,
      'filePattern': opts.file_pattern,
      'outputFile': outFile,
      'outputFormat': opts.output_format,
      'dryRun': opts.dry_run,
      'verbosity': opts.verbosity,
    })
