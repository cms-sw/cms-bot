#! /usr/bin/env python
"""
This script generates json file (like CMSSW_10_0_X.json) which is then used to render cmssdt ib page.
"""
from __future__ import print_function
from optparse import OptionParser
import subprocess
import re
import json
from pickle import Unpickler
from os.path import basename, dirname, exists, join, expanduser, getmtime
from glob import glob
from github import Github
from pprint import pformat

from cmsutils import get_config_map_properties
from github_utils import get_merge_prs
from cms_static import GH_CMSSW_REPO, GH_CMSSW_ORGANIZATION
from releases import CMSSW_DEVEL_BRANCH
from socket import setdefaulttimeout

setdefaulttimeout(120)
CMSSW_REPO_NAME = join(GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO)

# -----------------------------------------------------------------------------------
# ---- Parser Options
# -----------------------------------------------------------------------------------
parser = OptionParser(
    usage="usage: %prog CMSSW_REPO GITHUB_IO_REPO START_DATE"
          "\n CMSSW_REPO: location of the cmssw repository. This must be a bare clone ( git clone --bare )"
          "\n CMSDIST_REPO: location of the cmsdist repository. This must be a normal clone"
          "\n GITHUB_IO_REPO: location of the github.io repository. This must be a normal clone"
          "\n for example: cmssw.git or /afs/cern.ch/cms/git-cmssw-mirror/cmssw.git"
          "\n START_DATE: the date of the earliest IB to show. It must be in the format"
          "\n <year>-<day>-<month>-<hour>"
          "\n For example:"
          "\n 2014-10-08-1400"
)

parser.add_option("-v", "--verbose", dest="verbose", action="store_true", help="Do not post on Github", default=False)

(options, args) = parser.parse_args()

"""
-----------------------------------------------------------------------------------
---- Output Schema
-----------------------------------------------------------------------------------

comparisons": [ <DictA>, <DictB>, <DictC> ]

Each dict contains the result of the comparison between 2 tags in cmssw. For example 
CMSSW_5_3_X_2015-02-03-0200 with CMSSW_5_3_X_2015-02-04-0200 which correspond 
to the IB CMSSW_5_3_X_2015-02-04-0200

The schema of the dictionary is as folows:
{
   "addons": [],
   "builds": [],
   "fwlite": [],
   "compared_tags": "",
   "utests": [],
   "gpu_utests": [],
   "cmsdistTags": {},
   "relvals": [],
   "static_checks": "",
   "valgrind": "",
   "material_budget" : "",
   "isIB": Boolean,
   "tests_archs": [],
   "release_name": "",
   "merged_prs": [],
   "RVExceptions" : Boolean

}
"""


# -----------------------------------------------------------------------------------
# ---- Review of arguments
# -----------------------------------------------------------------------------------

if (len(args) < 4):
    print('not enough arguments\n')
    parser.print_help()
    exit()

# Remember that the cmssw repo is a bare clone while cmsdist is a complete clone
CMSSW_REPO_LOCAL = args[0]
GITHUB_IO_REPO = args[1]
CMSDIST_REPO = args[2]
START_DATE = args[3]
if len(args) >= 5:
    CMS_PRS = args[4]
else:
    CMS_PRS = "cms-prs"


# -----------------------------------------------------------------------------------
# ---- Fuctions
# -----------------------------------------------------------------------------------
def print_verbose(msg):
    """
    Takes into account the verbose option. If the option is activated it doesn't print anything.
    """
    if options.verbose:
        print (msg)


def parse_config_map_line(line):
    """
    reads a line of config.map and returns a dictionary with is parameters
    """
    params = {}
    parts = line.split(';')

    for part in parts:
        if part == '':
            continue
        key = part.split('=')[0]
        value = part.split('=')[1]
        params[key] = value

    return params


def get_config_map_params():
    """
    gets the list of architectures by reading config.map, they are saved in ARCHITECTURES
    gets the releases branches from config.map, they are saved in RELEASES_BRANCHES
    it maps the branches for all the releases this is to take into account the case in which the base branch
    is different from the release queue
    """
    f = open(CONFIG_MAP_FILE, 'r')
    for line in f.readlines():
        params = parse_config_map_line(line.rstrip())
        if not params: continue
        print(params)

        arch = params['SCRAM_ARCH']
        if arch not in ARCHITECTURES:
            ARCHITECTURES.append(arch)

        release_queue = params['RELEASE_QUEUE']
        base_branch = params.get('RELEASE_BRANCH')
        if base_branch:
            if base_branch == "master": base_branch = CMSSW_DEVEL_BRANCH
            RELEASES_BRANCHES[release_queue] = base_branch
        else:
            RELEASES_BRANCHES[release_queue] = release_queue

        sp_rel_name = release_queue.split('_')[3]

        if sp_rel_name != 'X' and sp_rel_name not in SPECIAL_RELEASES:
            SPECIAL_RELEASES.append(sp_rel_name)

        if (not params.get('DISABLED') or params.get('IB_WEB_PAGE')):
            if not RELEASES_ARCHS.get(release_queue):
                RELEASES_ARCHS_WITH_DIST_BRANCH[release_queue] = {}
                RELEASES_ARCHS[release_queue] = []
            RELEASES_ARCHS[release_queue].append(arch)
            RELEASES_ARCHS_WITH_DIST_BRANCH[release_queue][arch] = params['CMSDIST_TAG']
            if release_queue not in RELEASE_QUEUES:
                RELEASE_QUEUES.append(release_queue)

        additional_tests = params.get('ADDITIONAL_TESTS')

        if additional_tests:
            if RELEASE_ADITIONAL_TESTS.get(release_queue): continue
            RELEASE_ADITIONAL_TESTS[release_queue] = {}
            # if not RELEASE_ADITIONAL_TESTS.get( release_queue ):
            #  RELEASE_ADITIONAL_TESTS[ release_queue ] = {}
            RELEASE_ADITIONAL_TESTS[release_queue][arch] = [test for test in additional_tests.split(',') if
                                                            test != 'dqm']

    SP_REL_REGEX = "|".join(SPECIAL_RELEASES)
    RELEASE_QUEUES.sort()

    print()
    print('---------------------------')
    print('Read config.map:')
    print('ARCHS:')
    print(ARCHITECTURES)
    print('--')
    print(RELEASES_ARCHS)
    print('RELEASES_BRANCHES:')
    print(RELEASES_BRANCHES)
    print('special releases')
    print(SPECIAL_RELEASES)
    print('aditional tests')
    print(RELEASE_ADITIONAL_TESTS)
    print('I am going to show:')
    print(RELEASE_QUEUES)
    print('---------------------------')
    print()


def get_tags_from_line(line, release_queue):
    """
    reads a line of the output of git log and returns the tags that it contains
    if there are no tags it returns an empty list
    it applies filters according to the release queue to only get the
    tags related to the current release queue
    """
    if 'tags->' not in line:
        return []
    tags_str = line.split('tags->')[1]
    if re.match('.*SLHC$', release_queue):
        filter = release_queue[:-6] + '[X|0-9]_SLHC.*'
    else:
        filter = release_queue[:-1] + '[X|0-9].*'

    ## if the tags part is equal to ," there are no tags
    if tags_str != ',"':
        tags = tags_str.split(',', 1)[1].strip().replace('(', '').replace(')', '').split(',')
        # remove te word "tag: "
        tags = [t.replace('tag: ', '') for t in tags]
        # I also have to remove the branch name because it otherwise will always appear
        # I also remove tags that have the  string _DEBUG_TEST, they are used to create test IBs
        tags = [t for t in tags if re.match(filter, t.strip()) and (t.strip().replace('"', '') != release_queue) and (
                'DEBUG_TEST' not in t)]
        return [t.replace('"', '').replace('tag:', '').strip() for t in tags]
    else:
        return []


# -----------------------------------------------------------------------------------
# ---- Fuctions -- Analize Git outputs
# -----------------------------------------------------------------------------------
def determine_build_error(nErrorInfo):
    a = BuildResultsKeys.COMP_ERROR in nErrorInfo.keys()
    b = BuildResultsKeys.LINK_ERROR in nErrorInfo.keys()
    c = BuildResultsKeys.MISC_ERROR in nErrorInfo.keys()
    d = BuildResultsKeys.DWNL_ERROR in nErrorInfo.keys()
    e = BuildResultsKeys.DICT_ERROR in nErrorInfo.keys()
    f = BuildResultsKeys.PYTHON_ERROR in nErrorInfo.keys()
    return a or b or c or d or e or f


def determine_build_warning(nErrorInfo):
    a = BuildResultsKeys.PYTHON3_ERROR in nErrorInfo.keys()
    b = BuildResultsKeys.COMP_WARNING in nErrorInfo.keys()
    return a or b


def get_results_one_addOn_file(file):
    look_for_err_cmd = 'grep "failed" %s' % file
    result, err, ret_code = get_output_command(look_for_err_cmd)
    if ' 0 failed' in result:
        return True
    else:
        return False


def get_results_one_unitTests_file(file, grep_str="ERROR"):
    """
    given a unitTests-summary.log it determines if the test passed or not
    it returns a tuple, the first element is one of the possible values of PossibleUnitTestResults
    The second element is a dictionary which indicates how many tests failed
    """
    look_for_err_cmd = 'grep -h -c "%s" %s' % (grep_str, file)
    result, err, ret_code = get_output_command(look_for_err_cmd)

    result = result.rstrip()

    details = {'num_fails': result}

    if result != '0':
        return PossibleUnitTestResults.FAILED, details
    else:
        return PossibleUnitTestResults.PASSED, details


def get_results_one_relval_file(filename):
    """
    given a runall-report-step123-.log file it returns the result of the relvals
    it returns a tuple, the first element indicates if the tests passed or not
    the second element is a dictionary which shows the details of how many relvals pased
    and how many failed
    """
    summary_file = filename.replace("/runall-report-step123-.log", "/summary.json")
    if exists(summary_file) and getmtime(summary_file)>getmtime(filename):
        try:
            details = json.load(open(summary_file))
            return details['num_failed'] == 0, details
        except:
            pass

    details = {'num_passed': 0,
               'num_failed': 1,
               'known_failed': 0}

    print_verbose('Analyzing: ' + filename)
    lines = file(filename).read().split("\n")
    results = [x for x in lines if ' tests passed' in x]
    if len(results) == 0:
        return False, details
    out = results.pop()

    num_passed_sep = out.split(',')[0].replace(' tests passed', '').strip()
    num_failed_sep = out.split(',')[1].replace(' failed', '').strip()
    try:
        details["num_passed"] = sum([int(num) for num in num_passed_sep.split(' ')])
        details["num_failed"] = sum([int(num) for num in num_failed_sep.split(' ')])
    except ValueError as e:
        print("Error while reading file %s" % filename)
        print(e)
        return False, details
    with open(summary_file, "w") as ref:
      json.dump(details, ref)
    return details["num_failed"] == 0, details


def get_results_details_one_build_file(file, type):
    """
    Given a logAnalysis.pkl file, it determines if the tests passed or not
    it returns a tuple, the first element is one of the values of PossibleBuildResults
    The second element is a dictionary containing the details of the results.
    If the tests are all ok this dictionary is empty
    """
    summFile = open(file, 'r')
    pklr = Unpickler(summFile)
    [rel, plat, anaTime] = pklr.load()
    errorKeys = pklr.load()
    nErrorInfo = pklr.load()
    summFile.close()
    # if type=='builds':
    #  py3_log = join(dirname(dirname(file)),'python3.log')
    #  if exists (py3_log):
    #    py3 = open(py3_log, 'r')
    #    nErrorInfo[BuildResultsKeys.PYTHON3_ERROR]=len([l for l in py3.readlines() if ' Error compiling ' in l])

    if determine_build_error(nErrorInfo):
        return PossibleBuildResults.ERROR, nErrorInfo
    elif determine_build_warning(nErrorInfo):
        return PossibleBuildResults.WARNING, nErrorInfo
    else:
        return PossibleBuildResults.PASSED, nErrorInfo


def analyze_tests_results(output, results, arch, type):
    """
    parses the tests results for each file in output. It distinguishes if it is
    build, unit tests, relvals, or addon tests logs. The the result of the parsing
    is saved in the parameter results.
    type can be 'relvals', 'utests', 'gpu_tests', 'addON', 'builds', 'fwlite'

    schema of results:
    {
      "<IBName>": [ result_arch1, result_arch2, ... result_archN ]
    }
    schema of result_arch
    {
      "arch"    : "<architecture>"
      "file"    : "<location of the result>"
      "passed"  : <true or false> ( if not applicable the value is true )
      "details" : <details for the tests> ( can be empty if not applicable, but not undefined )
    }
    """
    for line in output.splitlines():
        m = re.search('/(CMSSW_[^/]+)/', line)
        if not m:
            print_verbose('Ignoring file:\n%s' % line)
            continue

        print("Processing ", type, ":", line)
        rel_name = m.group(1)
        result_arch = {}
        result_arch['arch'] = arch
        result_arch['file'] = line

        details = {}
        passed = None
        if type == 'relvals':
            passed, details = get_results_one_relval_file(line)
            result_arch['done'] = False
            if exists(join(dirname(line), "done")) or exists(join(dirname(line), "all.pages")):
                result_arch['done'] = True
        elif type == 'utests':
            passed, details = get_results_one_unitTests_file(line)
        elif type == 'gpu_utests':
            passed, details = get_results_one_unitTests_file(line)
        elif type == 'addOn':
            passed = get_results_one_addOn_file(line)
        elif type == 'builds':
            passed, details = get_results_details_one_build_file(line, type)
        elif type == 'fwlite':
            passed, details = get_results_details_one_build_file(line, type)
        elif type == 'python3':
            passed, details = get_results_one_unitTests_file(line, " Error compiling ")
        elif type == 'invalid-includes':
            errs = len(json.load(open(line)))
            if errs:
                passed = PossibleUnitTestResults.FAILED
                details = {'num_fails': str(errs)}
            else:
                passed = PossibleUnitTestResults.PASSED
        else:
            print('not a valid test type %s' % type)
            exit(1)

        result_arch['passed'] = passed
        result_arch['details'] = details

        if rel_name not in results.keys():
            results[rel_name] = []

        results[rel_name].append(result_arch)


def execute_magic_command_find_rv_exceptions_results():
    """
    Searchs in github.io for the results for relvals exceptions
    """
    print ('Finding relval exceptions results...')
    command_to_execute = MAGIC_COMMAND_FIND_EXCEPTIONS_RESULTS_RELVALS
    out, err, ret_code = get_output_command(command_to_execute)

    rv_exception_results = {}

    for line in out.splitlines():
        line_parts = line.split('/')
        ib_name = line_parts[-1].replace('EXCEPTIONS.json', '') + line_parts[-2]
        rv_exception_results[ib_name] = True

    return rv_exception_results


def get_tags(git_log_output, release_queue):
    """
    returns a list of tags based on git log output
    It uses the release queue name to filter the tags, this avoids having
    in the result tags from other queues that may come from automatic merges.
    For example, if release_queue is 7_2_X, it will drop tags like CMSSW_7_2_THREADED_X_2014-09-15-0200
    """
    tags = []
    for line in git_log_output.splitlines():
        tags += get_tags_from_line(line, release_queue)

    if (len(tags) == 0):
        print("ATTENTION:")
        print("looks like %s has not changed between the tags specified!" % release_queue)
        command_to_execute = MAGIC_COMMAND_FIND_FIRST_MERGE_WITH_TAG.replace('END_TAG', release_queue)
        out, err, ret_code = get_output_command(command_to_execute)
        print(out)
        tags = get_tags_from_line(out, release_queue)
        print(tags)

    return tags


def get_day_number_tag(tag):
    """
    returns the number of the day of a tag
    if it is not an IB tag, it returns -1
    """
    parts = tag.split("-")
    if len(parts) == 1:
        return -1
    else:
        day = parts[2]
        try:
            return int(day)
        except ValueError:
            return -1


def is_tag_list_suspicious(tags):
    """
    uses some heuristics to tell if the list of tags seems to be too short
    """
    if len(tags) < 7:
        return True
    day_first_tag = get_day_number_tag(tags[-1])
    day_second_tag = get_day_number_tag(tags[-2])
    return day_second_tag - day_first_tag > 1


def is_recent_branch(err):
    """
    determines if  the error is because one of the tags does not exist
    this can happen when the branch that is being analyzed has been
    created recently
    """
    return "unknown revision or path not in the working tree" in err


# -----------------------------------------------------------------------------------
# ---- Fuctions -- Execute Magic commands
# -----------------------------------------------------------------------------------

def look_for_missing_tags(start_tag, release_queue):
    """
    this calls the git log command with the first tag to look for missing
    tags that were not found previously
    """
    command_to_execute = MAGIC_COMMAND_FIND_FIRST_MERGE_WITH_TAG.replace('END_TAG', start_tag)
    out, err, ret_code = get_output_command(command_to_execute)
    tags = get_tags_from_line(out, release_queue)
    return tags


def get_output_command(command_to_execute):
    """
    Executes the command that is given as parameter, returns a tuple out,err,ret_code
    with the output, error and return code obtained
    """
    print_verbose('Executing:')
    print_verbose(command_to_execute)

    p = subprocess.Popen(command_to_execute, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    ret_code = p.returncode

    if ret_code != 0:
        print_verbose(ret_code)
        print_verbose('Error:')
        print_verbose(err)

    return out, err, ret_code


def execute_magic_command_tags(start_tag, end_tag, release_queue, release_branch, ignore_tags=None):
    """
    Gets the tags between start_tag and end_tag, the release_queue is used as a filter
    to ignore tags that are from other releases
    """
    print_verbose('Release Queue:')
    print_verbose(release_queue)
    print_verbose('Release Branch:')
    print_verbose(release_branch)

    # if it is a special release queue based on a branch with a different name, I use the release_branch as end tag
    if release_queue == release_branch:
        print_verbose('These IBs have a custom release branch')
        real_end_tag = end_tag
    else:
        real_end_tag = release_branch

    print_verbose('Start tag:')
    print_verbose(start_tag)
    print_verbose('End tag:')
    print_verbose(real_end_tag)
    command_to_execute = MAGIC_COMMAND_TAGS.replace('START_TAG', start_tag).replace('END_TAG', real_end_tag)
    command_to_execute = command_to_execute.replace('RELEASE_QUEUE',release_queue)
    print("Running:", command_to_execute)
    out, err, ret_code = get_output_command(command_to_execute)

    # check if the end_tag exists, but the start_tag doesn't
    # this could mean that the release branch has been created recently
    if ret_code != 0:
        if is_recent_branch(err):
            print_verbose('looks like this branch has been created recently')
            command_to_execute = MAGIC_COMMAND_FIND_ALL_TAGS.replace('END_TAG', real_end_tag).replace('RELEASE_QUEUE',
                                                                                                      release_queue)
            print("Running:", command_to_execute)
            out, err, ret_code = get_output_command(command_to_execute)

    tags = get_tags(out, release_queue)
    tags.append(start_tag)

    # check if the tags list could be missing tags
    # this means that the release branch has not changed much from the start_tag
    if is_tag_list_suspicious(tags):
        print_verbose('this list could be missing something!')
        print_verbose(tags)
        new_tags = look_for_missing_tags(start_tag, release_branch)
        tags.pop()
        tags += new_tags

    tags = [t for t in reversed(tags) if not ignore_tags or not re.match(ignore_tags, t)]
    print("Found Tags:", tags)

    return tags


def execute_command_compare_tags(branch, start_tag, end_tag, git_dir, repo, cache={}):
    comp = {}
    comp['compared_tags'] = '%s-->%s' % (start_tag, end_tag)
    comp['release_name'] = end_tag
    notes = get_merge_prs(start_tag, end_tag, git_dir, CMS_PRS, cache)
    prs = []
    for pr_num in notes:
        pr = {'is_merge_commit': False, 'from_merge_commit': False}
        if notes[pr_num]['branch'] != "master":
            if notes[pr_num]['branch'] != branch: pr['from_merge_commit'] = True
        pr['number'] = pr_num
        pr['hash'] = notes[pr_num]['hash']
        pr['author_login'] = notes[pr_num]['author']
        pr['title'] = notes[pr_num]['title']
        pr['url'] = 'https://github.com/cms-sw/cmssw/pull/%s' % pr_num
        prs.append(pr)
    comp['merged_prs'] = prs
    return comp


def compare_tags(branch, tags, git_dir, repo, cache={}):
    comparisons = []
    if len(tags) > 1: comparisons.append(execute_command_compare_tags(branch, tags[0], tags[0], git_dir, repo, cache))
    for i in range(len(tags) - 1):
        comp = execute_command_compare_tags(branch, tags[i], tags[i + 1], git_dir, repo, cache)
        comparisons.append(comp)
    return comparisons


def execute_magic_command_get_cmsdist_tags():
    """
    Executes the command to get the tags schema of all_tags_found:
    {
      "<IBName>": {
                    "<arch_name>" : "<tag_name>"
                  }
    }
    """
    all_tags_found = {}
    for arch in ARCHITECTURES:
        command_to_execute = MAGIC_COMMAND_CMSDIST_TAGS.replace('ARCHITECTURE', arch)
        out, err, ret_code = get_output_command(command_to_execute)

        for line in out.splitlines():
            m = re.search('CMSSW.*[0-9]/', line)
            if not m: continue

            rel_name = line[m.start():m.end() - 1]

            if not all_tags_found.get(rel_name):
                all_tags_found[rel_name] = {}

            all_tags_found[rel_name][arch] = line
            if "CMSSW_10_" in rel_name: print("CMSDIST ", rel_name, arch)
    return all_tags_found


def execute_magic_command_find_results(type):
    """
    Executes the a command to get the results for the relvals, unit tests,
    addon tests, and compitlation tests
    It saves the results in the parameter 'results'
    type can be 'relvals', 'utests', 'gpu_tests', 'addON', 'builds'
    """
    ex_magix_comand_finf_setuls_dict = {
        'relvals': MAGIC_COMMAD_FIND_RESULTS_RELVALS,
        'utests': MAGIC_COMMAND_FIND_RESULTS_UNIT_TESTS,
        'gpu_utests': MAGIC_COMMAND_FIND_RESULTS_GPU_UNIT_TESTS,
        'addOn': MAGIC_COMMAND_FIND_RESULTS_ADDON,
        'builds': MAGIC_COMMAND_FIND_RESULTS_BUILD,
        'fwlite': MAGIC_COMMAND_FIND_RESULTS_FWLITE,
        'python3': MAGIC_COMMAND_FIND_RESULTS_PYTHON3,
        'invalid-includes': MAGIC_COMMAND_FIND_INVALID_INCLUDES
    }
    if type not in ex_magix_comand_finf_setuls_dict:
        print('not a valid test type %s' % type)
        exit(1)
    results = {}
    for arch in ARCHITECTURES:
        base_command = ex_magix_comand_finf_setuls_dict[type]
        command_to_execute = base_command.replace('ARCHITECTURE', arch)
        print("Run>>", command_to_execute)
        out, err, ret_code = get_output_command(command_to_execute)
        analyze_tests_results(out, results, arch, type)
    return results


def print_results(results):
    print("Results:")
    print()
    print()
    for rq in results:
        print()
        print(rq['release_name'])
        print('/////////////////////////')
        for comp in rq['comparisons']:
            print(comp['compared_tags'])

            print('\t' + 'HLT Tests: ' + comp['hlt_tests'])
            print('\t' + 'Crab Tests: ' + comp['crab_tests'])
            print('\t' + 'HEADER Tests:' + comp['check-headers'])
            print('\t' + 'DQM Tests: ' + comp['dqm_tests'])
            print('\t' + 'Static Checks: ' + comp['static_checks'])
            print('\t' + 'Valgrind: ' + comp['valgrind'])
            print('\t' + 'Material budget: ' + comp['material_budget'])
            print('\t' + 'Igprof: ' + comp['igprof'])
            print('\t' + 'Profiling: ' + comp['profiling'])
            print('\t' + 'Comparison Baseline: ' + comp['comp_baseline'])
            print('\t' + 'Comparison Baseline State: ' + comp['comp_baseline_state'])

            cmsdist_tags = comp['cmsdistTags']
            print('\t' + 'cmsdist Tags:' + str(cmsdist_tags))

            builds_results = [res['arch'] + ':' + str(res['passed']) + ':' + str(res['details']) for res in
                              comp['builds']]
            print('\t' + 'Builds:' + str(builds_results))

            fwlite_results = [res['arch'] + ':' + str(res['passed']) + ':' + str(res['details']) for res in
                              comp['fwlite']]
            print('\t' + 'FWLite:' + str(fwlite_results))

            relvals_results = [res['arch'] + ':' + str(res['passed']) + ":" + str(res['details']) for res in
                               comp['relvals']]
            print('\t' + 'RelVals:' + str(relvals_results))

            utests_results = [res['arch'] + ':' + str(res['passed']) + ':' + str(res['details']) for res in
                              comp['utests']]
            print('\t' + 'UnitTests:' + str(utests_results))

            gpu_utests_results = [res['arch'] + ':' + str(res['passed']) + ':' + str(res['details']) for res in
                                  comp['gpu_utests']]
            print('\t' + 'GPUUnitTests:' + str(gpu_utests_results))

            addons_results = [res['arch'] + ':' + str(res['passed']) for res in comp['addons']]
            print('\t' + 'AddOns:' + str(addons_results))

            merged_prs = [pr['number'] for pr in comp['merged_prs']]
            print('\t' + 'PRs:' + str(merged_prs))
            print('\t' + "Cmsdist compared tags: " + pformat(comp['cmsdist_compared_tags']))
            print('\t' + "Cmsdist merged prs: " + pformat(comp['cmsdist_merged_prs']))

            from_merge_commit = [pr['number'] for pr in comp['merged_prs'] if pr['from_merge_commit']]
            print('\t' + 'From merge commit' + str(from_merge_commit))

            print('\t' + 'RVExceptions: ' + str(comp.get('RVExceptions')))
            print('\t' + 'inProgress: ' + str(comp.get('inProgress')))


def fill_missing_cmsdist_tags(results):
    """
    Iterates over the IBs comparisons, if an IB doesn't have a tag for an architecture, the previous tag is
    assigned. For example, for arch slc6_amd64_gcc481
    1. CMSSW_7_1_X_2014-10-02-1500 was built using the tag IB/CMSSW_7_1_X_2014-10-02-1500/slc6_amd64_gcc481
    2. There is no tag for CMSSW_7_1_X_2014-10-03-0200 in cmsdist
    Then, it assumes that the tag used for CMSSW_7_1_X_2014-10-03-0200 was IB/CMSSW_7_1_X_2014-10-02-1500/slc6_amd64_gcc481
    """
    for rq in results:
        previous_cmsdist_tags = {}
        for comp in rq['comparisons']:
            for arch in comp['tests_archs']:
                current_ib_tag_arch = comp['cmsdistTags'].get(arch)
                if current_ib_tag_arch:
                    previous_cmsdist_tags[arch] = current_ib_tag_arch
                else:
                    if previous_cmsdist_tags.get(arch):
                        comp['cmsdistTags'][arch] = previous_cmsdist_tags[arch]
                    else:
                        comp['cmsdistTags'][arch] = 'Not Found'


def get_cmsdist_merge_commits(results):
    """
    Will modiffy object in place
    """
    for release_queue in results:
        previous_cmsdist_tags = {}
        release_queue_name = release_queue['release_name']
        for pos, comp in enumerate(release_queue['comparisons'], start=1):
            comp['cmsdist_merged_prs'] = {}
            comp['cmsdist_compared_tags'] = {}

            if pos == len(release_queue['comparisons']):
                # this is special case when we want to compare unreleased IB with branch head
                # sinces it is not an IB, there are no build archs yet.
                archs_to_iterate_over = RELEASES_ARCHS[release_queue_name]
            else:
                archs_to_iterate_over = comp['tests_archs']

            for arch in archs_to_iterate_over:
                if arch not in RELEASES_ARCHS_WITH_DIST_BRANCH[release_queue_name]: continue
                cmsdist_branch = RELEASES_ARCHS_WITH_DIST_BRANCH[release_queue_name][arch]
                if pos == len(release_queue['comparisons']):
                    # if this last comparison, it means its not yet an IB
                    # we want to compare branch HEAD with last tag
                    # we will compare with remote branch to avoid checking out all the time, this is the reason for
                    # remotes/origin/{BRANCH_NAME}
                    current_ib_tag_arch = "remotes/origin/" + cmsdist_branch
                    # when dumping JSON, we do not want 'remotes/origin/ part
                    current_ib_tag_arch_to_show = cmsdist_branch
                else:
                    # else, just use current cmsdistTag
                    current_ib_tag_arch = comp['cmsdistTags'].get(arch)
                    current_ib_tag_arch_to_show = comp['cmsdistTags'].get(arch)
                if arch in previous_cmsdist_tags:
                    previous_cmsdist_tag = previous_cmsdist_tags[arch]
                else:
                    previous_cmsdist_tag = current_ib_tag_arch

                previous_cmsdist_tags[arch] = current_ib_tag_arch
                notes = get_merge_prs(previous_cmsdist_tag, current_ib_tag_arch, "{0}/.git".format(CMSDIST_REPO), CMS_PRS, repo_name='cmsdist')
                prs = []
                for pr_num in notes:
                    pr = {'is_merge_commit': False, 'from_merge_commit': False}
                    if notes[pr_num]['branch'] != "master":
                        if notes[pr_num]['branch'] != cmsdist_branch:
                            pr['from_merge_commit'] = True
                    pr['number'] = pr_num
                    pr['hash'] = notes[pr_num]['hash']
                    pr['author_login'] = notes[pr_num]['author']
                    pr['title'] = notes[pr_num]['title']
                    pr['url'] = 'https://github.com/cms-sw/cmsdist/pull/%s' % pr_num
                    prs.append(pr)
                comp['cmsdist_merged_prs'][arch] = prs
                comp['cmsdist_compared_tags'][arch] = "{0}..{1}".format(previous_cmsdist_tag, current_ib_tag_arch_to_show)


def add_tests_to_results(results, unit_tests, relvals_results,
                         addon_results, build_results, cmsdist_tags_results,
                         rv_Exceptions_Results, fwlite_results, gpu_unit_tests, python3_results, invalid_includes):
    """
    merges the results of the tests with the structure of the IBs tags and the pull requests
    it also marks the comparisons that correspond to an IB
    """
    for rq in results:
        for comp in rq['comparisons']:
            rel_name = comp['compared_tags'].split('-->')[1]
            rvsres = relvals_results.get(rel_name)
            utres = unit_tests.get(rel_name)
            gpu_utres = gpu_unit_tests.get(rel_name)
            python3_res = python3_results.get(rel_name)
            invalid_includes_res = invalid_includes.get(rel_name)
            adonres = addon_results.get(rel_name)
            buildsres = build_results.get(rel_name)
            fwliteres = fwlite_results.get(rel_name)
            cmsdist_tags = cmsdist_tags_results.get(rel_name)
            print("CMDIST ", rel_name, ":", cmsdist_tags)

            # for tests with arrays
            comp['relvals'] = rvsres if rvsres else []
            comp['utests'] = utres if utres else []
            comp['gpu_utests'] = gpu_utres if gpu_utres else []
            comp['python3_tests'] = python3_res if python3_res else []
            comp['invalid_includes'] = invalid_includes_res if invalid_includes_res else []
            comp['addons'] = adonres if adonres else []
            comp['builds'] = buildsres if buildsres else []
            comp['fwlite'] = fwliteres if fwliteres else []
            comp['cmsdistTags'] = cmsdist_tags if cmsdist_tags else {}
            comp['isIB'] = '-' in rel_name
            comp['RVExceptions'] = rv_Exceptions_Results.get(rel_name)
            if "_X_" in rel_name:
                comp['ib_date'] = rel_name.split("_X_", 1)[-1]
            else:
                comp['ib_date'] = ''

            comp['inProgress'] = False
            if not comp.get('static_checks'):
                comp['static_checks'] = 'not-found'
            if not comp.get('hlt_tests'):
                comp['hlt_tests'] = 'not-found'
            if not comp.get('crab_tests'):
                comp['crab_tests'] = 'not-found'
            if not comp.get('check-headers'):
                comp['check-headers'] = 'not-found'
            if not comp.get('valgrind'):
                comp['valgrind'] = 'not-found'
            if not comp.get('material_budget'):
                comp['material_budget'] = 'not-found'
            if not comp.get('igprof'):
                comp['igprof'] = 'not-found'
            if not comp.get('profiling'):
                comp['profiling'] = 'not-found'
            if not comp.get('comp_baseline'):
                comp['comp_baseline'] = 'not-found'
                comp['comp_baseline_state'] = 'errors'
            if not comp.get('dqm_tests'):
                comp['dqm_tests'] = 'not-found'
            # custom details for new IB page
            if not comp.get('material_budget_v2'):
                comp['material_budget_v2'] = 'not-found'
            if not comp.get('material_budget_comparison'):
                comp['material_budget_comparison'] = 'not-found'
            if not comp.get('static_checks_v2'):
                comp['static_checks_v2'] = 'not-found'
            if not comp.get('static_checks_failures'):
                comp['static_checks_failures'] = 'not-found'

            a = [t['arch'] for t in utres] if utres else []
            b = [t['arch'] for t in rvsres] if rvsres else []
            c = [t['arch'] for t in buildsres] if buildsres else []

            not_complete_archs = [arch for arch in c if arch not in a]
            for nca in not_complete_archs:
                result = {}
                result['arch'] = nca
                result['file'] = str([res['file'] for res in buildsres if res['arch'] == nca])
                result['passed'] = PossibleUnitTestResults.UNKNOWN
                result['details'] = {}
                comp['utests'].append(result)

            comp['tests_archs'] = list(set(a + b + c))


def find_comparison_baseline_results(comparisons, architecture):
    """
    Finds for an IB the results of the Comparison BaseLine
    """
    for comp in comparisons:
        rel_name = comp['compared_tags'].split('-->')[1]
        print('Looking for comparison baseline results for ', rel_name)
        comp['comp_baseline'] = find_one_comparison_baseline(rel_name, architecture)
        comp['comp_baseline_state'] = "errors"
        if comp['comp_baseline'] != 'not-found':
            comp['comp_baseline_state'] = find_one_comparison_baseline_errors(rel_name, architecture)


def find_material_budget_results(comparisons, architecture):
    """
    Finds for an IB the results of the material_budget
    """
    for comp in comparisons:
        rel_name = comp['compared_tags'].split('-->')[1]
        print('Looking for material_budget results for ', rel_name)
        arch, comparison, status = find_one_material_budget(rel_name, architecture)
        if (arch is None):
            comp['material_budget'] = status  # returns 'inprogress'
        else:
            comp['material_budget'] = arch + ":" + comparison
        comp['material_budget_v2'] = {
            'status': status,
            'arch': arch
        }
        if (comparison is None) or (comparison is '-1'):
            pass
        elif (comparison == "0"):
            comp['material_budget_comparison'] = {'status': 'found', 'results': 'ok', 'arch': arch}
        else:
            comp['material_budget_comparison'] = {'status': 'found', 'results': 'warning', 'arch': arch}


def find_one_test_results(command_to_execute):
    print("Running ", command_to_execute)
    out, err, ret_code = get_output_command(command_to_execute)
    print("Ran:", out, err, ret_code, command_to_execute)
    if ret_code == 0:
        print('found')
        return 'found'
    print('inprogress')
    return 'inprogress'


# def find_dup_dict_result(command_to_execute):
#     # todo delete
#     print("Running ", command_to_execute)
#     out, err, ret_code = get_output_command(command_to_execute)
#     print("Ran:", out, err, ret_code, command_to_execute)
#     if ret_code == 0:
#         if int(out) == 0:
#             print('passed')
#             return 'passed'
#         else:
#             print('error')
#             return 'error'
#     print("not-found")
#     return("not-found")


def find_dup_dict_result(comparisons):
    """
    Will check for duplicated dictionary (CMSSW specific test) for each architecture
    """
    def get_status(command_to_execute):
        print("Running ", command_to_execute)
        out, err, ret_code = get_output_command(command_to_execute)
        print("Ran:", out, err, ret_code, command_to_execute)
        if ret_code == 0:
            if int(out) == 0:
                print('passed')
                return 'passed'
            else:
                print('error')
                return 'error'
        print("not-found")
        return ("not-found")

    test_field = "dupDict"
    for comp in comparisons:
        if test_field not in comp:
            comp[test_field] = []
        for architecture in comp["tests_archs"]:
            rel_name = comp['compared_tags'].split('-->')[1]
            print("Looking for {0} results for {1}.".format(test_field,rel_name))
            command_to_execute = MAGIC_COMMAND_FIND_DUP_DICT.replace('RELEASE_NAME', rel_name).replace(
                'ARCHITECTURE', architecture
            )
            comp[test_field].append({
                "passed": get_status(command_to_execute),
                "arch": architecture
            })


def find_one_profiling_result(magic_command):
    """
    Looks for one profiling result
    """
    command_to_execute = magic_command.replace('WORKFLOW', '11834.21')
    print("Running ", command_to_execute)
    out, err, ret_code = get_output_command(command_to_execute)
    print("Ran:", out, err, ret_code, command_to_execute)
    file = out.strip()
    if (ret_code == 0) and (out != ""):
        print('found', file)
        return {'status' : 'passed', 'data' : file}
    print('inprogress')
    return 'inprogress'



def find_general_test_results(test_field, comparisons, architecture, magic_command, results_function=find_one_test_results):
    """
    Finds for results for the test_field. Modifies `comparisons` dict in place.
    :param comparisons: comparison dictionary
    :param architecture: arch
    :param magic_command: string with bash command to execute
    :param test_field: field to write back the results to
    :param results_function: function how to process results
    """

    for comp in comparisons:
        rel_name = comp['compared_tags'].split('-->')[1]
        print("Looking for {0} results for {1}.".format(test_field,rel_name))
        command_to_execute = magic_command.replace('RELEASE_NAME', rel_name).replace('ARCHITECTURE', architecture)
        comp[test_field] = results_function(command_to_execute)


def find_general_test_results_2(test_field, comparisons, magic_command):
    def find_one_test_results(release_name):
        command = magic_command.replace('RELEASE_NAME', release_name)
        out, err, ret_code = get_output_command(command)
        if ret_code == 0:
            print('found')
            return 'found'
        print('not-found')
        return 'not-found'

    for comp in comparisons:
        rel_name = comp['compared_tags'].split('-->')[1]
        print("Looking for {0} results for {1}.".format(test_field, rel_name))
        comp[test_field] = find_one_test_results(rel_name)


def find_and_check_result(release_name, architecture, magic_cmd, res_cmd, opt_cmd=''):
    path = magic_cmd.replace('RELEASE_NAME', release_name)
    path = path.replace('ARCHITECTURE', architecture)
    _, _, t_ret_code = get_output_command('test -e ' + path)


    def set_result(cmd, status0='passed', statusnon0='error'):
        cmd =  cmd.format(path)
        out, err, ret_code = get_output_command(cmd)
        try:
            e = 0 
            for o in [ x for x in out.split('\n') if x]:
                e += int(o)
            if e == 0:
                result = status0
            else:
                result = statusnon0
        except:
            print("ERROR running command: " + cmd)
            print(out, err, ret_code)
            result = 'error'  # this will make sure to check what is wrong with the file
        return result


    if t_ret_code == 0:
        result = set_result(res_cmd)
        if result == 'passed' and opt_cmd != '':
            result =  set_result(opt_cmd, 'passed', 'inprogress')
    else:
        result = 'inprogress'

    print(result)
    return result


def find_check_hlt(comparisons, architecture):
    for comp in comparisons:
        rel_name = comp['compared_tags'].split('-->')[1]
        print("Looking for {0} results for {1}.".format('hlt', rel_name))
        comp['hlt_tests'] = find_and_check_result(rel_name, architecture, CHECK_HLT_PATH, 'grep -h -c "exit status: *[1-9]" {0}')


def find_check_crab(comparisons, architecture):
    for comp in comparisons:
        rel_name = comp['compared_tags'].split('-->')[1]
        print("Looking for {0} results for {1}.".format('crab', rel_name))
        comp['crab_tests'] = find_and_check_result(rel_name, architecture, CHECK_CRAB_PATH, 'grep -h -c "FAILED" {0}/*/statusfile', 'grep -h -c "INPROGRESS" {0}/*/statusfile')


def find_check_headers(comparisons, architecture):
    for comp in comparisons:
        rel_name = comp['compared_tags'].split('-->')[1]
        print('Looking for check-headers results for', rel_name, '.')
        comp['check-headers'] = find_and_check_result(rel_name, architecture, CHECK_HEADERS_PATH, 'cat {0} | wc -l')


def find_ubsan_logs(comparisons, ubsan_data):
    for c in comparisons:
        rel_name = c['compared_tags'].split('-->')[1]
        if rel_name in ubsan_data:
            print('Looking for ubsan results for', rel_name, '.')
            if ubsan_data[rel_name]>0:
                c['ubsan-logs'] = 'error'
            else:
                c['ubsan-logs'] = 'passed'


def find_static_results(comparisons, architecture):
    """
    Finds for an IB the results of the static tests
    """
    for comp in comparisons:
        rel_name = comp['compared_tags'].split('-->')[1]
        print('Looking for static tests results for ', rel_name)
        comp['static_checks'] = find_one_static_check(rel_name, architecture)
        # For new IB page
        if (comp['static_checks'] == 'not-found' or comp['static_checks'] == 'inprogress'):
            comp['static_checks_v2'] = comp['static_checks']
        else:
            resultList = comp['static_checks'].split(":")
            comp['static_checks_v2'] = {'status': "passed", 'arch': resultList[0]}
            iterable = []
            for i in range(1, len(resultList)):
                result = resultList[i]
                if result == '':
                    continue
                iterable.append(result)
            if (len(iterable) > 0):
                comp['static_checks_failures'] = {
                    'status': "found",
                    'arch': resultList[0],
                    'iterable': iterable
                }

def find_one_static_filter_check(release_name, architecture, magic_cmd):
    """
    Looks for one static-tests-filter result for the IB, if it finds it, the value is 'found' if not, the value is 'inprogress'
    """
    command_to_execute = magic_cmd.replace('RELEASE_NAME', release_name)
    command_to_execute = command_to_execute.replace('ARCHITECTURE', architecture)
    print("Running ", command_to_execute)
    out, err, ret_code = get_output_command(command_to_execute)
    print("Ran:", out, err, ret_code, command_to_execute)
    return out


def find_one_static_check(release_name, architecture):
    """
    Looks for one static-tests result for the IB, if it finds it, the value is 'found' if not, the value is 'inprogress'
    """
    command_to_execute = MAGIC_COMMAND_FIND_STATIC_CHECKS.replace('RELEASE_NAME', release_name)
    command_to_execute = command_to_execute.replace('ARCHITECTURE', architecture)
    print("Running ", command_to_execute)
    out, err, ret_code = get_output_command(command_to_execute)
    print("Ran:", out, err, ret_code, command_to_execute)
    if ret_code == 0:
        arch = out.split()[0]
        print('found', arch)
        filter1 = find_one_static_filter_check(release_name, arch, MAGIC_COMMAND_FIND_STATIC_CHECKS_FILTER1)
        return arch + ":" + filter1
    print('inprogress')
    return 'inprogress'


def find_one_material_budget(release_name, architecture):
    """
    Looks for one material_budget result for the IB, if it finds it, the value is 'found' if not, the value is 'inprogress'
    """
    command_to_execute = MAGIC_COMMAND_FIND_MATERIL_BUDGET_CHECKS.replace('RELEASE_NAME', release_name)
    command_to_execute = command_to_execute.replace('ARCHITECTURE', architecture)
    print("Running ", command_to_execute)
    out, err, ret_code = get_output_command(command_to_execute)
    print("Ran:", out, err, ret_code, command_to_execute)
    if ret_code == 0:
        arch = out.split()[0]
        print('found', arch)
        command_to_execute = MAGIC_COMMAND_FIND_MATERIL_BUDGET_COMPARISON_CHECKS.replace('RELEASE_NAME',
                                                                                         release_name).replace(
            'ARCHITECTURE', architecture)
        print("Running ", command_to_execute)
        out, err, ret_code = get_output_command(command_to_execute)
        if ret_code == 0:
            return (arch, out.split()[0], 'found')
        return (arch, "-1", 'found')
    print('inprogress')
    return (None, None, 'inprogress')


def find_one_comparison_baseline_errors(release_name, architecture):
    """
    Looks for one comparison baseline errors result for the IB, if no errors then value is 'ok' if not,
    the value is 'errors'
    """
    command_to_execute = MAGIC_COMMAND_COMPARISON_BASELINE_ERRORS.replace('RELEASE_NAME', release_name)
    command_to_execute = command_to_execute.replace('ARCHITECTURE', architecture)
    print("Running ", command_to_execute)
    out, err, ret_code = get_output_command(command_to_execute)
    print("Ran:", out, err, ret_code, command_to_execute)
    if out == "":
        return "ok"
    else:
        return "errors"


def find_one_comparison_baseline(release_name, architecture):
    """
    Looks for one comparison baseline result for the IB, if it finds it, the value is 'found' if not, the value is ''
    """
    command_to_execute = MAGIC_COMMAND_FIND_COMPARISON_BASELINE.replace('RELEASE_NAME', release_name)
    command_to_execute = command_to_execute.replace('ARCHITECTURE', architecture)
    print("Running ", command_to_execute)
    out, err, ret_code = get_output_command(command_to_execute)
    print("Ran:", out, err, ret_code, command_to_execute)
    if ret_code == 0:
        print('found')
        return COMPARISON_BASELINE_TESTS_URL.replace('RELEASE_NAME', release_name).replace('ARCHITECTURE', architecture)
    print('inprogress')
    return 'inprogress'


def generate_separated_json_results(results):
    """
    reads the results and generates a separated json for each release_queue
    it also generates a csv file with statistics per release_queue and a general one
    """
    all_ibs_list = []
    all_prs_list = []

    for rq in results:
        file_name = rq['release_name'] + ".json"
        summary_file_name = rq['release_name'] + "_summary.txt"
        out_json = open(file_name, "w")
        json.dump(rq, out_json, indent=4)
        out_json.close()

        f_summary = open(summary_file_name, "w")
        ibs = [comp['release_name'] for comp in rq['comparisons']
               if (comp['release_name'] != rq['base_branch']) and comp['isIB']]

        all_ibs_list.extend(ibs)

        # Ignore forward ported prs, and merge commits
        only_prs_list = []
        for comp in rq['comparisons']:
            only_prs_list.extend([pr['number'] for pr in comp['merged_prs']
                                  if not (pr['is_merge_commit'] or pr['from_merge_commit'])])

        all_prs_list.extend(only_prs_list)
        f_summary.write("IBs:%s\n" % ibs)
        f_summary.write("NumIBs:%d\n" % len(ibs))
        f_summary.write("PRs:%s\n" % only_prs_list)
        f_summary.write("NumPRs:%d\n" % len(only_prs_list))
        f_summary.close()

    all_ibs_list = list(set(all_ibs_list))
    all_ibs_list.sort()

    all_prs_list = list(set(all_prs_list))
    all_prs_list.sort()

    f_summary_all = open('ibsSummaryAll.txt', "w")
    f_summary_all.write("IBs:%s\n" % all_ibs_list)
    f_summary_all.write("NumIBs:%d\n" % len(all_ibs_list))

    f_summary_all.write("PRs:%s\n" % all_prs_list)
    f_summary_all.write("NumPRs:%d\n" % len(all_prs_list))


def get_production_archs(config_map):
    archs = {}
    for release in config_map:
        if (('PROD_ARCH' in release) and (('DISABLED' not in release) or ('IB_WEB_PAGE' in release))):
            archs[release['RELEASE_QUEUE']] = release['SCRAM_ARCH']
    return archs


def generate_ib_json_short_summary(results):
    """
    Generates a json file with the global status of the last IB for each architecture,
    per each  Release Queue
    Schema of short_summary
    [ releaseQueue1, releaseQueue2, ... , releaseQueueN ]
    Schema of releaseQueueN
    {
       "<ReleaseQueue>": {
                           "<arch>": {
                                       "status": "ok|warning|error|unknown"
                                       "latest_IB" : "<latest IB>"
                                     }
                         }
    }
    """
    short_summary = {}
    for rq in results:
        # this should not be called 'release name', this should be fixed
        rq_name = rq['release_name']
        enabled_archs = RELEASES_ARCHS[rq_name]
        for arch in enabled_archs:
            ibs_for_current_arch = [rel for rel in rq['comparisons'] if arch in rel["tests_archs"]]
            # it starts as ok and checks the conditions
            ib_status = 'ok'

            if len(ibs_for_current_arch) == 0:
                pass
                # TODO unused
                # latest_IB = 'N/A'
                # ib_status = 'unknown'
            else:
                latest_IB_info = ibs_for_current_arch[-1]
                latest_IB_name = latest_IB_info['release_name']

                build_info = [b for b in latest_IB_info["builds"] if b['arch'] == arch]
                if len(build_info) == 0:
                    build_passed = 'unknown'
                else:
                    build_passed = build_info[0]["passed"]

                fwlite_info = [b for b in latest_IB_info["fwlite"] if b['arch'] == arch]
                # TODO unused
                # if len(fwlite_info) == 0:
                #     fwlite_passed = 'unknown'
                # else:
                #     fwlite_passed = build_info[0]["passed"]

                unit_tests_info = [u for u in latest_IB_info["utests"] if u['arch'] == arch]
                if len(unit_tests_info) == 0:
                    utests_passed = 'unknown'
                else:
                    utests_passed = unit_tests_info[0]["passed"]

                gpu_unit_tests_info = [u for u in latest_IB_info["gpu_utests"] if u['arch'] == arch]
                if len(gpu_unit_tests_info) == 0:
                    gpu_utests_passed = 'unknown'
                else:
                    gpu_utests_passed = gpu_unit_tests_info[0]["passed"]

                relvals_info = [r for r in latest_IB_info["relvals"] if r['arch'] == arch]
                if len(relvals_info) == 0:
                    relvals_passed = 'unknown'
                else:
                    relvals_passed = relvals_info[0]["passed"]

                if not short_summary.get(rq_name):
                    short_summary[rq_name] = {}
                short_summary[rq_name][arch] = {}
                short_summary[rq_name][arch]["latest_IB"] = latest_IB_name

                merged_statuses = "%s-%s-%s-%s" % (build_passed, utests_passed, relvals_passed, gpu_utests_passed)

                if 'unknown' in merged_statuses:
                    ib_status = 'unknown'
                elif 'failed' in merged_statuses or 'False' in merged_statuses:
                    ib_status = 'error'
                elif 'warning' in merged_statuses:
                    ib_status = 'warning'
                short_summary[rq_name][arch]["status"] = ib_status

    short_summary['all_archs'] = ARCHITECTURES
    short_summary['prod_archs'] = get_production_archs(get_config_map_properties())
    out_json = open('LatestIBsSummary.json', "w")
    json.dump(short_summary, out_json, indent=4)
    out_json.close()


def identify_release_groups(results):
    """
    Identifies and groups the releases accodring to their prefix
    For example if the release queues are:
    CMSSW_7_1_X, CMSSW_7_0_X, CMSSW_6_2_X, CMSSW_5_3_X, CMSSW_7_1_THREADED_X
    CMSSW_7_1_BOOSTIO_X, CMSSW_7_1_ROOT6_X, CMSSW_7_1_GEANT10_X, CMSSW_6_2_X_SLHC
    CMSSW_7_1_DEVEL_X, CMSSW_7_1_CLANG_X, CMSSW_7_2_X, CMSSW_7_2_DEVEL_X, CMSSW_7_2_CLANG_X
    CMSSW_7_2_GEANT10_X
    It will organize them like this:
    CMSSW_5_3_X: CMSSW_5_3_X
    CMSSW_7_2_X: CMSSW_7_2_X, CMSSW_7_2_DEVEL_X, CMSSW_7_2_CLANG_X, CMSSW_7_2_GEANT10_X
    CMSSW_6_2_X: CMSSW_6_2_X CMSSW_6_2_X_SLHC
    CMSSW_7_0_X: CMSSW_7_0_X
    CMSSW_7_1_X: CMSSW_7_1_X, CMSSW_7_1_THREADED_X, CMSSW_7_1_BOOSTIO_X, CMSSW_7_1_ROOT6_X',
                 CMSSW_7_1_GEANT10_X, CMSSW_7_1_DEVEL_X, CMSSW_7_1_CLANG_X
    It returns a dictionary in which the keys are the release prefixes, and the values are
    the release queues
    """
    from operator import itemgetter

    releases = []
    release_objs = {}
    for rq in results:
        rn = rq['release_name']
        release_objs[rn] = rq
        releases.append([rn] + [int(x) for x in rn.split("_")[1:3]])

    groups = []
    for item in sorted(releases, key=itemgetter(1, 2)):
        prefix = "CMSSW_" + "_".join([str(s) for s in item[1:3]]) + "_X"
        group = None
        for g in groups:
            if g[0] == prefix:
                group = g
                break
        if not group:
            group = [prefix, []]
            groups.append(group)
        if not item[0] in group[1]: group[1].append(item[0])

    structure = {'all_release_queues': [], 'all_prefixes': [], 'default_release': ''}
    for g in groups:
        rq = g[0]
        structure[rq] = sorted(g[1], reverse=True)
        structure['all_release_queues'] = structure[rq] + structure['all_release_queues']
        structure['all_prefixes'].append(rq)
    for rq in structure['all_prefixes'][::-1]:
        rn = structure[rq][0]
        if (rn in release_objs) and ('comparisons' in release_objs[rn]) and (release_objs[rn]['comparisons']):
            for comp in release_objs[rn]['comparisons']:
                if ('builds' in comp) and (comp['builds']):
                    structure['default_release'] = rn
                    return structure
    return structure


def fix_results(results):
    for rq in results:
        prev_ib_date = ''
        release_count = 0
        for comp in rq['comparisons']:
            comp['release_queue'] = rq['release_name']
            comp['base_branch'] = rq['base_branch']
            if comp['ib_date']:
                prev_ib_date = comp['ib_date']
                release_count = 0
                comp['ib_date'] = prev_ib_date + '-0000'
            else:
                release_count += 1
                xstr = str(format(release_count, '04d'))
                if not prev_ib_date:
                    comp['ib_date'] = xstr + '-' + comp['release_name']
                else:
                    comp['ib_date'] = prev_ib_date + '-' + xstr
            comp['next_ib'] = False
            if comp['release_name'] == rq['base_branch']: comp['next_ib'] = True
        rq['comparisons'].reverse()


# -----------------------------------------------------------------------------------
# ---- Start of execution
# -----------------------------------------------------------------------------------

if __name__ == "__main__":

    MAGIC_COMMAND_CMSDIST_TAGS = "pushd %s; git tag -l '*/*/ARCHITECTURE' | grep -E 'IB|ERR'; popd" % CMSDIST_REPO
    CMSSDT_DIR = "/data/sdt"
    BUILD_LOG_DIR = CMSSDT_DIR + "/buildlogs"
    JENKINS_ARTIFACTS_SUBDIR = "SDT/jenkins-artifacts"
    JENKINS_ARTIFACTS_DIR = CMSSDT_DIR + "/" + JENKINS_ARTIFACTS_SUBDIR
    # I used this type of concatenation because the string has %s inside
    MAGIC_COMMAND_FIND_FIRST_MERGE_WITH_TAG = 'GIT_DIR=' + CMSSW_REPO_LOCAL + ' git log --pretty=\'"%s", "tags->,%d"\' END_TAG | grep "\\\"tags->," | head -n1'
    MAGIC_COMMAD_FIND_RESULTS_RELVALS = 'find ' + BUILD_LOG_DIR + '/ARCHITECTURE/www  -mindepth 6 -maxdepth 6 -path "*/pyRelValMatrixLogs/run/runall-report-step123-.log"'
    MAGIC_COMMAND_FIND_EXCEPTIONS_RESULTS_RELVALS = "find cms-sw.github.io/data/relvals/ -name '*EXCEPTIONS.json'"
    MAGIC_COMMAND_TAGS = 'GIT_DIR=' + CMSSW_REPO_LOCAL + ' git log --pretty=\'"%s", "tags->,%d"\' START_TAG..END_TAG | grep -E "\\\"tags->, " | grep -E "RELEASE_QUEUE"'
    MAGIC_COMMAND_FIND_RESULTS_UNIT_TESTS = 'find ' + BUILD_LOG_DIR + '/ARCHITECTURE/www -mindepth 4 -maxdepth 4 -name unitTests-summary.log'
    MAGIC_COMMAND_FIND_RESULTS_GPU_UNIT_TESTS = 'find ' + BUILD_LOG_DIR + '/ARCHITECTURE/www -mindepth 5 -maxdepth 5 -name unitTests-summary.log | grep "/GPU/"'
    MAGIC_COMMAND_FIND_RESULTS_ADDON = 'find ' + BUILD_LOG_DIR + '/ARCHITECTURE/www -mindepth 4 -maxdepth 4 -name addOnTests.log'
    MAGIC_COMMAND_FIND_RESULTS_BUILD = 'find ' + BUILD_LOG_DIR + '/ARCHITECTURE/www  -mindepth 5 -maxdepth 5 -path "*/new/logAnalysis.pkl"'
    MAGIC_COMMAND_FIND_RESULTS_FWLITE = 'find ' + BUILD_LOG_DIR + '/ARCHITECTURE/www  -mindepth 5 -maxdepth 5 -path "*/new_FWLITE/logAnalysis.pkl"'
    MAGIC_COMMAND_FIND_RESULTS_PYTHON3 = 'find ' + BUILD_LOG_DIR + '/ARCHITECTURE/www -mindepth 4 -maxdepth 4 -name python3.html'
    MAGIC_COMMAND_FIND_INVALID_INCLUDES = 'find ' + JENKINS_ARTIFACTS_DIR + '/invalid-includes -maxdepth 3 -mindepth 3 -path "*/ARCHITECTURE/summary.json" -type f'
    MAGIC_COMMAND_FIND_STATIC_CHECKS = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/ib-static-analysis/RELEASE_NAME && ls ' + JENKINS_ARTIFACTS_DIR + '/ib-static-analysis/RELEASE_NAME/'
    MAGIC_COMMAND_FIND_STATIC_CHECKS_FILTER1 = 'test -s ' + JENKINS_ARTIFACTS_DIR + '/ib-static-analysis/RELEASE_NAME/ARCHITECTURE/reports/modules2statics-filter1.txt && echo reports/modules2statics-filter1.txt'
    MAGIC_COMMAND_FIND_MATERIL_BUDGET_CHECKS = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/material-budget/RELEASE_NAME && ls ' + JENKINS_ARTIFACTS_DIR + '/material-budget/RELEASE_NAME/'
    MAGIC_COMMAND_FIND_MATERIL_BUDGET_COMPARISON_CHECKS = "TEST_FILE=" + JENKINS_ARTIFACTS_DIR + "/material-budget/RELEASE_NAME/ARCHITECTURE/comparison/Images/MBDiff.txt && test -f $TEST_FILE && grep '0$' $TEST_FILE | wc -l"
    MAGIC_COMMAND_FIND_VALGRIND = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/valgrind/RELEASE_NAME'
    MAGIC_COMMAND_FIND_IGPROF = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/igprof/RELEASE_NAME'
    MAGIC_COMMAND_FIND_PROFILING = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/profiling/RELEASE_NAME'
    MAGIC_COMMAND_FIND_PROFILING_CHECKS_FILTER1 = 'ls '+JENKINS_ARTIFACTS_DIR+'/profiling/RELEASE_NAME/ARCHITECTURE/WORKFLOW/step3_*.resources.json 2>/dev/null | head -1 | sed "s|.*/RELEASE_NAME/||;s|.json$||"'
    MAGIC_COMMAND_FIND_PROFILING_CHECKS_FILTER2 = 'ls ' + JENKINS_ARTIFACTS_DIR + '/igprof/RELEASE_NAME/ARCHITECTURE/profiling/*/sorted_RES_CPU_step3.txt 2>/dev/null | head -1 | sed "s|.*/RELEASE_NAME/||"'
    MAGIC_COMMAND_FIND_PROFILING_CHECKS_FILTER3 = 'ls ' + JENKINS_ARTIFACTS_DIR + '/profiling/RELEASE_NAME/ARCHITECTURE/*/step3_gpu_nsys.txt 2>/dev/null | head -1 | sed "s|.*/RELEASE_NAME||"'
    MAGIC_COMMAND_FIND_COMPARISON_BASELINE = 'test -f ' + JENKINS_ARTIFACTS_DIR + '/ib-baseline-tests/RELEASE_NAME/ARCHITECTURE/-GenuineIntel/matrix-results/wf_errors.txt'
    MAGIC_COMMAND_COMPARISON_BASELINE_ERRORS = 'cat ' + JENKINS_ARTIFACTS_DIR + '/ib-baseline-tests/RELEASE_NAME/ARCHITECTURE/-GenuineIntel/matrix-results/wf_errors.txt'
    COMPARISON_BASELINE_TESTS_URL = 'https://cmssdt.cern.ch/' + JENKINS_ARTIFACTS_SUBDIR + '/ib-baseline-tests/RELEASE_NAME/ARCHITECTURE/-GenuineIntel/matrix-results'
    CHECK_HLT_PATH = JENKINS_ARTIFACTS_DIR + '/HLT-Validation/RELEASE_NAME/ARCHITECTURE/jenkins.log'
    CHECK_CRAB_PATH = JENKINS_ARTIFACTS_DIR + '/ib-run-crab/RELEASE_NAME/*'
    MAGIC_COMMAND_FIND_DQM_TESTS = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/ib-dqm-tests/RELEASE_NAME'
    MAGIC_COMMAND_FIND_LIZARD = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/lizard/RELEASE_NAME/ARCHITECTURE'
    MAGIC_COMMAND_FIND_CHECK_HEADERS = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/check_headers/RELEASE_NAME/ARCHITECTURE'
    CHECK_HEADERS_PATH = JENKINS_ARTIFACTS_DIR + '/check_headers/RELEASE_NAME/ARCHITECTURE/headers_with_error.log'
    CHECK_UBSANLOG_PATH = JENKINS_ARTIFACTS_DIR + '/ubsan_logs/CMSSW_*/ubsan_runtime_errors.log'
    MAGIC_COMMAND_FIND_FLAWFINDER = 'test -d ' + JENKINS_ARTIFACTS_DIR + '/flawfinder/RELEASE_NAME/ARCHITECTURE'
    MAGIC_COMMAND_FIND_DUP_DICT = ("grep -v '^Searching for '  " + BUILD_LOG_DIR + "/ARCHITECTURE/www/*/*/RELEASE_NAME/testLogs/dup*.log" +
        " |  grep -v ':**** SKIPPING ' | grep -v '^ *$'  | wc -l ")
    CONFIG_MAP_FILE = 'config.map'
    # this will be filled using config.map by get_config_map_params()
    ARCHITECTURES = []
    # this will be filled using config.map by get_config_map_params()
    RELEASES_BRANCHES = {}
    # this will be filled using config.map by get_config_map_params() SLHC releases have a different format, so it is hardcoded
    SPECIAL_RELEASES = ['SLHC']
    # this will be filled using config.map by get_config_map_params()
    SP_REL_REGEX = ""  # Needs to be declared empty before using
    # These are the release queues that need to be shown, this this will be filled using config.map by get_config_map_params()
    RELEASE_QUEUES = []
    # These are the ibs and archs for which the aditional tests need to be shown
    # The schema is:
    # {
    #   "<IBName>": {
    #                 "<architecture>" : [ test1, test2, ... , testN ]
    #               }
    # }
    # This this will be filled using config.map by get_config_map_params()
    RELEASE_ADITIONAL_TESTS = {}
    # the acrhitectures for which the enabled releases are currently avaiable
    # The schema is:
    # {
    #   "<IBName>": [ "arch1" , "arch2" , ... ,"archN" ]
    # }
    # will be filled using config.map by get_config_map_params()
    RELEASES_ARCHS = {}
    """
    {
        "RELEASE_QUE" : { "ARCH1" : "CMSDIST_BRANCH", "ARCH2" : "CMSDIST_BRANCH2" } 
    }
    """
    RELEASES_ARCHS_WITH_DIST_BRANCH = {}
    # The IBs and arch for which relval results are availavle
    # The schema is:
    # {
    #   "<IBName>": [ "arch1" , "arch2" , ... ,"archN" ]
    # }
    MAGIC_COMMAND_FIND_ALL_TAGS = 'GIT_DIR=' + CMSSW_REPO_LOCAL + ' git log --pretty=\'"%s", "tags->,%d"\' END_TAG | grep -E "\\\"tags->, " | grep -E "RELEASE_QUEUE"'
    # This regular expression allows to identify if a merge commit is an automatic forward port
    AUTO_FORWARD_PORT_REGEX = '^.*Merge CMSSW.+ into CMSSW.+$'


    class BuildResultsKeys(object):
        DICT_ERROR = 'dictError'
        COMP_ERROR = 'compError'
        LINK_ERROR = 'linkError'
        COMP_WARNING = 'compWarning'
        DWNL_ERROR = 'dwnlError'
        MISC_ERROR = 'miscError'
        IGNORE_WARNING = 'ignoreWarning'
        PYTHON_ERROR = 'pythonError'
        PYTHON3_ERROR = 'python3Warning'


    class PossibleBuildResults(object):
        PASSED = 'passed'
        WARNING = 'warning'
        ERROR = 'error'


    class PossibleUnitTestResults(object):
        PASSED = 'passed'
        FAILED = 'failed'
        UNKNOWN = 'unknown'


    results = []

    get_config_map_params()
    SP_REL_REGEX = "|".join(SPECIAL_RELEASES)
    REQUESTED_COMPARISONS = [('%s_%s..%s' % (rq, START_DATE, rq)) for rq in RELEASE_QUEUES]

    AFS_INSTALLATION = "/cvmfs/cms.cern.ch/*/cms"
    installedPaths = []
    for ib_path in [ "/cvmfs/cms-ib.cern.ch", "/cvmfs/cms-ib.cern.ch/sw/*"]:
        installedPaths += [x for x in glob(ib_path + "/week*/*/cms/cmssw/*")]
        installedPaths += [x for x in glob(ib_path + "/week*/*/cms/cmssw-patch/*")]
    installedPaths += [x for x in glob(AFS_INSTALLATION + "/cmssw/*")]
    installedPaths += [x for x in glob(AFS_INSTALLATION + "/cmssw-patch/*")]

    installedReleases = [basename(x) for x in installedPaths]

    print_verbose('Installed Releases:')
    print_verbose(installedReleases)
    prs_file = GITHUB_IO_REPO + "/_data/prs_cmssw_cache.json"
    token = open(expanduser("~/.github-token")).read().strip()
    github = Github(login_or_token=token)
    CMSSW_REPO = github.get_repo(CMSSW_REPO_NAME)

    for comp in REQUESTED_COMPARISONS:
        start_tag = comp.split("..")[0]
        end_tag = comp.split("..")[1]
        release_queue = start_tag

        # if is a SLHC or any special release, the split will happen with the fifth underscore _
        if re.search(SP_REL_REGEX, release_queue):
            print_verbose('This is a special release')
            release_queue = re.match(r'^((?:[^_]*_){%d}[^_]*)_(.*)' % (4), release_queue).groups()[0]
        else:
            release_queue = re.match(r'^((?:[^_]*_){%d}[^_]*)_(.*)' % (3), release_queue).groups()[0]

        print('####################################################################')
        print("I will analyze %s from %s to %s:" % (release_queue, start_tag, end_tag))

        release_branch = RELEASES_BRANCHES[release_queue]
        release_queue_results = {}
        release_queue_results['release_name'] = release_queue
        release_queue_results['base_branch'] = release_branch

        print('Identifying tags...')
        tags = execute_magic_command_tags(start_tag, end_tag, release_queue, release_branch,
                                          ignore_tags="^CMSSW_9_3_.+_2017-09-(06-2300|07-1100)$")
        originalTags = tags
        tags = [x for x in tags if x in installedReleases]  # NOTE: comment out on local development
        tags.append(release_branch)
        print('I got these tags: ')
        print(tags)

        print('Getting merged pull requests between tags...')
        release_queue_results['comparisons'] = compare_tags(release_branch, tags, CMSSW_REPO_LOCAL, CMSSW_REPO)
        print('Done')

        # It checks if the tests are being run for that architecture, if they don't, it doesn't look for them.
        # Then it goes over each selected tests, executes 'magic' command to look for tests results, interprets it
        # and writes back in to 'release_queue_results['comparisons']'. Finally, it appends it back to results object.
        # (check config.map file)
        additional_tests = RELEASE_ADITIONAL_TESTS.get(release_queue)
        if additional_tests:
            for arch in additional_tests.keys():
                tests_to_find = additional_tests[arch]
                if 'HLT' in tests_to_find:
                    find_check_hlt(release_queue_results['comparisons'], arch)
                if 'crab' in tests_to_find:
                    find_check_crab(release_queue_results['comparisons'], arch)
                if 'static-checks' in tests_to_find:
                    find_static_results(release_queue_results['comparisons'], arch)
                if 'material-budget' in tests_to_find:
                    find_material_budget_results(release_queue_results['comparisons'], arch)
                if 'baseline' in tests_to_find:
                    find_comparison_baseline_results(release_queue_results['comparisons'], arch)
                if 'valgrind' in tests_to_find:
                    find_general_test_results(
                        'valgrind', release_queue_results['comparisons'], arch, MAGIC_COMMAND_FIND_VALGRIND
                    )
                if 'lizard' in tests_to_find:
                    find_general_test_results(
                        'lizard', release_queue_results['comparisons'], arch, MAGIC_COMMAND_FIND_LIZARD
                    )
                if 'flawfinder' in tests_to_find:
                    find_general_test_results(
                        'flawfinder',  release_queue_results['comparisons'], arch, MAGIC_COMMAND_FIND_FLAWFINDER
                    )
                if ('igprof-mp' in tests_to_find) or ('igprof-pp' in tests_to_find):
                    find_general_test_results(
                        'igprof', release_queue_results['comparisons'], arch, MAGIC_COMMAND_FIND_IGPROF
                    )
                if ('profiling' in tests_to_find):
                    find_general_test_results(
                        'profiling', release_queue_results['comparisons'], arch, MAGIC_COMMAND_FIND_PROFILING
                        )
                    find_general_test_results(
                        'piechart', release_queue_results['comparisons'], arch, MAGIC_COMMAND_FIND_PROFILING_CHECKS_FILTER1, find_one_profiling_result
                        )
                    find_general_test_results(
                        'reco_event_loop', release_queue_results['comparisons'], arch, MAGIC_COMMAND_FIND_PROFILING_CHECKS_FILTER2, find_one_profiling_result
                        )
                    find_general_test_results(
                        'reco_gpu_mods', release_queue_results['comparisons'], arch, MAGIC_COMMAND_FIND_PROFILING_CHECKS_FILTER3, find_one_profiling_result
                        )
                if 'check-headers' in tests_to_find:
                    find_check_headers(release_queue_results['comparisons'], arch)
                # will run every time for Q/A, that is why not checked if it is in tests to find

        find_general_test_results_2(
            'dqm_tests', release_queue_results['comparisons'], MAGIC_COMMAND_FIND_DQM_TESTS
        )
        results.append(release_queue_results)

    add_tests_to_results(
        results,
        execute_magic_command_find_results('utests'),
        execute_magic_command_find_results('relvals'),
        execute_magic_command_find_results('addOn'),
        execute_magic_command_find_results('builds'),
        execute_magic_command_get_cmsdist_tags(),
        execute_magic_command_find_rv_exceptions_results(),  # rv_Exceptions_Results
        execute_magic_command_find_results('fwlite'),
        execute_magic_command_find_results('gpu_utests'),
        execute_magic_command_find_results('python3'),
        execute_magic_command_find_results('invalid-includes')
    )

    ubsan_data = {}
    out, err, rcode = get_output_command('wc -l %s' % CHECK_UBSANLOG_PATH)
    for line in out.split('\n'):
        if not '/CMSSW_' in line: continue
        print('UBSAN',line)
        count, rel = line.strip().split(' ',1)
        rel = rel.split('/')[-2]
        ubsan_data[rel]=int(count)
        if '_UBSAN_' in rel:
            ubsan_data[rel.replace('_UBSAN_','_')]=int(count)

    for release_queue_results in results:
        find_dup_dict_result(release_queue_results['comparisons'])
        find_ubsan_logs(release_queue_results['comparisons'], ubsan_data)

    fill_missing_cmsdist_tags(results)
    get_cmsdist_merge_commits(results)
    print_results(results)

    structure = identify_release_groups(results)
    fix_results(results)
    generate_separated_json_results(results)
    generate_ib_json_short_summary(results)

    out_json = open("merged_prs_summary.json", "w")
    json.dump(results, out_json, indent=4)
    out_json.close()

    out_groups = open("structure.json", "w")
    json.dump(structure, out_groups, indent=4)
    out_groups.close()
