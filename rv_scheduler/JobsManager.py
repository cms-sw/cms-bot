__author__ = 'mrodozov@cern.ch'
'''
This class instance(singleton) manages jobs ordering
'''
import psutil
import json
import subprocess
import os
import sys
import time

from Singleton import Singleton
from threading import Lock, Thread, Semaphore
from time import sleep
from operator import itemgetter

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CMS_BOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, CMS_BOT_DIR)
sys.path.insert(0, os.path.join(CMS_BOT_DIR, 'jobs'))

# from workflow_final import upload_logs

'''
method putNextJobsOnQueue may need to use another lock
whenever it starts to prevent method getFinishedJobs while loop to
get called more than once while putNextJobsOnQueue is still
executing 

'''


def relval_test_process(job=None):
    # unpack the job and execute
    # jobID, jobStep, jobCumulativeTime, jobSelfTime, jobCommands = job.items()
    jobID = job[0]
    jobStep = job[1]
    jobCumulativeTime = job[2]
    jobSelfTime = job[3]
    jobMem = job[4]
    jobCPU = job[5]
    jobCommands = job[6]
    prevJobExit = job[7]
    jobSelfTime = 0.001

    startTime = int(time.time())

    while True:
        # print 'eta: ', jobID, jobStep, jobSelfTime
        sleep(jobSelfTime)
        jobSelfTime -= 0.001
        if 0 > jobSelfTime:
            print 'breaking'
            break

    #have some delay for the test
    sleep(2)

    endTime = int(time.time())

    # return {'id': jobID, 'step': jobStep, 'exit_code': 0, 'mem': int(jobMem)}
    return {'id': jobID, 'step': jobStep, 'exit_code': '0', 'mem': int(jobMem), 'cpu': int(jobCPU),
            'stdout': 'notRun', 'stderr': 'notRun', 'startTime': startTime, 'endTime': endTime}


def process_relval_workflow_step(job=None):
    # unpack the job and execute
    # jobID, jobStep, jobCumulativeTime, jobSelfTime, jobCommands = job.items()
    jobID = job[0]
    jobStep = job[1]
    jobCumulativeTime = job[2]
    jobSelfTime = job[3]
    jobMem = job[4]
    jobCPU = job[5]
    jobCommands = job[6]
    prevJobExit = job[7]
    # jobCommands = 'ls'

    exit_code = 0

    if prevJobExit is not 0:
        return {'id': jobID, 'step': jobStep, 'exit_code': -1, 'mem': int(jobMem), 'cpu': int(jobCPU),
                'stdout': 'notRun', 'stderr': 'notRun', 'startTime': 0, 'endTime': 0}

    start_time = int(time.time())

    child_process = subprocess.Popen(jobCommands, shell=True)
    # , stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
    stdout = ''
    stderr = ''
    # child_process.communicate()
    # exit_code = child_process.returncode
    exit_code = os.waitpid(child_process.pid, 0)[1]
    # to test the non zero exit code

    endTime = int(time.time())

    return {'id': jobID, 'step': jobStep, 'exit_code': exit_code, 'mem': int(jobMem), 'cpu': int(jobCPU),
            'stdout': stdout, 'stderr': stderr, 'startTime': start_time, 'endTime': endTime}
    # start a subprocess, return it's output


def getWorkflowDuration(workflowFolder=None):
    total_time = 0
    for i in os.listdir(workflowFolder):
        if i.find('wf_stats-') is not -1:
            with open(os.path.join(workflowFolder, i), 'r') as wf_stats_file:
                wf_stats_obj = json.loads(wf_stats_file.read())
                total_time += wf_stats_obj[-1]['time']

    print total_time
    with open(os.path.join(workflowFolder, 'time.log'), 'w') as timelog_file:
        timelog_file.write(str(total_time))

    return total_time


def writeWorkflowLog(workflowFolder=None, workflowLogsJson=None):
    result_keys = sorted(workflowLogsJson, reverse=False)
    result_keys.remove('finishing_exit')
    workflow_subfolder = workflowFolder.split('/')[-1]
    print 'workflow subfolder is:', workflow_subfolder
    steps_strings = []
    time_string = ''
    exit_codes = []
    passed = []
    failed = []
    # print workflow_subfolder
    for i in result_keys:

        # print i, workflowLogsJson[i]
        if workflowLogsJson[i]['exit_code'] is 0:
            steps_strings.append(i + '-PASSED')
            passed.append('1')
            failed.append('0')
            exit_codes.append('0')
        elif workflowLogsJson[i]['exit_code'] is 'notRun':
            steps_strings.append(i + '-NOTRUN')
            passed.append('0')
            failed.append('0')
            exit_codes.append('0')
        else:
            steps_strings.append(i + '-FAILED')
            passed.append('0')
            failed.append('1')
            exit_codes.append(str(workflowLogsJson[i]['exit_code']))

    output_log = workflow_subfolder + ' ' + \
                 ' '.join(steps_strings) + ' ' + \
                 ' - time;' + ' ' + \
                 'exit:' + ' ' + \
                 ' '.join(exit_codes) + ' ' + \
                 '\n' + ' ' + \
                 ' '.join(passed) + ' test passed,' + ' ' + \
                 ' '.join(failed) + ' tests failed'
    print output_log

    with open(os.path.join(workflowFolder, 'workflow.log'), 'w') as wflog_output:
        wflog_output.write(output_log)
    # put also the hostname
    with open(os.path.join(workflowFolder, 'hostname'), 'w') as hostname_output:
        hostname_output.write(os.uname()[1])

def getAverageStatsFromJSONlogs(aLog=None):
    print aLog

'''
callbacks to be hooked
'''

def worklowIsStartingFunc(workflowID=None, wf_base_folder=None):
    print 'print from wf is starting'
    wfs_base = wf_base_folder.rsplit('/', 1)[0]
    print workflowID, wf_base_folder, wfs_base
    job_description = None
    with open(os.path.join(wfs_base,'jobs.json'),'r') as jobs_file:
        stats_obj = json.loads(jobs_file.read())
        for obj in stats_obj['jobs']:
            #print 'object is ', obj
            if 'name' in obj and obj['name'] == workflowID:
                print 'object is ', obj
                job_description = obj
                break
    if job_description:
        num_of_jobs = len(job_description['commands'])
        jobs_commands = job_description['commands']
        comm_num = 0
        new_jobs_commnds = []
        for comm in jobs_commands:
            comm['jobid'] = workflowID+'('+str(comm_num+1)+'/'+str(num_of_jobs)+')'
            comm['state'] = 'Pending'
            comm['exec_time'] = 0
            comm['start_time'] = 0
            comm['end_time'] = 0
            comm['exit_code'] = -1
            new_jobs_commnds.append(comm)
            comm_num += 1
        job_description['commands'] = new_jobs_commnds
        job_description['state'] = 'Done'
        with open(os.path.join(wfs_base, workflowID+'.json'), 'w') as job_file:
            job_file.write(json.dumps(job_description, indent=1, sort_keys=True))

def finilazeWorkflow(workflowID=None, wf_base_folder=None, job_results=None):
    print 'wf duration (all steps): ', getWorkflowDuration(wf_base_folder)
    print workflowID, wf_base_folder, job_results
    #writeWorkflowLog(wf_base_folder, job_results) #finishing function will fix this
    print 'finishing from callback'
    wfs_base = wf_base_folder.rsplit('/', 1)[0]
    steps_keys = job_results.keys()
    steps_keys.remove('finishing_exit')
    steps_keys = sorted(steps_keys)
    print 'sorted keys are: ', steps_keys
    wf_stats = {}
    with open(os.path.join(wfs_base, workflowID+'.json'),'r') as job_file:
        wf_stats = json.loads(job_file.read())
    cmmnd_cntr = 0
    new_cmmnds = []
    for cmmnd in wf_stats['commands']:
        cmmnds_element = cmmnd
        cmmnds_element['exit_code'] = job_results[steps_keys[cmmnd_cntr]]['exit_code']
        cmmnds_element['start_time'] = job_results[steps_keys[cmmnd_cntr]]['start_time']
        cmmnds_element['end_time'] = job_results[steps_keys[cmmnd_cntr]]['end_time']
        cmmnds_element['exec_time'] = job_results[steps_keys[cmmnd_cntr]]['exec_time']
        new_cmmnds.append(cmmnds_element)
        cmmnd_cntr += 1
    
    wf_stats['commands'] = new_cmmnds
    with open(os.path.join(wfs_base, workflowID+'.json'),'w') as job_file:
        job_file.write(json.dumps(wf_stats, indent=1, sort_keys=True))
    
    with open(os.path.join(wf_base_folder, 'hostname'), 'w') as hostname_output:
        hostname_output.write(os.uname()[1])
    
    os.chdir(wfs_base)
    #this is weird, try to put it in a function only. or put it in a try catch
    p=subprocess.Popen("%s/jobs/workflow_final.py %s" % (CMS_BOT_DIR, workflowID+'.json'), shell=True)
    e=os.waitpid(p.pid,0)[1]
    if e: exit(e)
    

def stepIsStartingFunc(workflowID=None, workflowStep=None, wf_base_folder=None):

    print 'print from step is starting'
    print workflowID, workflowStep, wf_base_folder
    wfs_base = wf_base_folder.rsplit('/', 1)[0]
    #with open(os.path.join(wfs_base, workflowID+'.json'),'a') as job_file:
    #    job_file.write('step '+ workflowStep + ' is starting \n')


def stepIsFinishingFunc(workflowID=None, workflowStep=None, wf_base_folder=None):

    print 'print from step is finishing'
    print workflowID, workflowStep, wf_base_folder
    wfs_base = wf_base_folder.rsplit('/', 1)[0]
    #with open(os.path.join(wfs_base, workflowID+'.json'),'a') as job_file:
    #    job_file.write('step '+ workflowStep + ' is finishing \n')

'''
end of callbacks. you are shooting a fly with bazooka here. whatever
'''

class workerThread(Thread):
    def __init__(self, target, *args):
        super(workerThread, self).__init__()
        self._target = target
        self._args = args
        # self.name = str(args[0] + ' ' + args[1])
        self.resultQueue = None
        self.getNextJobs = None

    def run(self):
        result = self._target(*self._args)
        # put the result when the task is finished
        # result = result+' '+self.name
        self.resultQueue.put(result)


class JobsManager(object):
    __metaclass__ = Singleton

    def __init__(self, jobs=None):

        self.jobs = jobs
        self.jobs_result_folders = {}
        self.started_jobs = None
        self.results = {}
        self.availableMemory = None
        self.availableCPU = None
        self.jobs_lock = Lock()  # lock when touching jobs structure
        self.started_jobs_lock = Lock()
        self.results_lock = Lock()  # lock when touching results structure
        self.error_codes_map = None
        self.translate_exit_codes = False  # set this flag to true to translate codes

        ''' 
        add the thread jobs that put jobs on execution queue
        and finilizes them here
        '''

        self.started_jobs = []  # jobs already started
        self.putJobsOnProcessQueue = Thread(target=self.putJobsOnQueue)
        self.getProcessedJobs = Thread(target=self.getFinishedJobs)
        self.toProcessQueue = None
        self.processedQueue = None
        self.getNextJobsEvent = None
        self.counter = Semaphore()

        '''
        API calls provided externally as functions that would be called with specific arguments
        '''

        self.workflowIsStarting = worklowIsStartingFunc
        self.workflowIsFinishing = finilazeWorkflow
        self.stepIsStarting = stepIsStartingFunc
        self.stepIsFinishing = stepIsFinishingFunc

    '''
    methods to check resources availability
    '''

    def checkIfEnoughMemory(self, mem_value=0):
        return self.availableMemory > mem_value
        # or use a record of the remaining memory

    def checkIfEnoughCPU(self, cpu_value=0):
        return self.availableCPU > cpu_value

    '''
    put jobs for processing methods
    '''

    def putJobsOnQueue(self):

        while True:
            if not self.jobs:
                print 'to process queue completed, breaking put jobs on queue', '\n'
                break

            # get jobs from the structure put them on queue to process
            self.counter.acquire()  # acquire resource once, the finishing thread would release it for each finished job
            next_jobs = self.getNextJobs()
            print 'put jobs on queue getting next jobs:', '\n'  # , next_jobs
            self.putNextJobsOnQueue(next_jobs)

    def getNextJobs(self, sort_function=None):
        next_jobs = []
        with self.jobs_lock:
            for i in self.jobs:

                if not self.jobs[i].keys():
                    continue
                '''
                check if the prev job had finished with exit != 0 and if it did, 
                '''

                prev_exit = 0
                with self.results_lock:
                    if i in self.results:
                        for s in self.results[i]:
                            if self.results[i][s]['exit_code'] is not 0:
                                prev_exit = self.results[i][s]['exit_code']
                                break

                current_step = sorted(self.jobs[i].keys())[0]
                if i not in self.jobs_result_folders:
                    self.jobs_result_folders[i] = self.jobs[i][current_step]['results_folder']
                cumulative_time = sum([self.jobs[i][j]['avg_time'] for j in self.jobs[i]])
                element = (i, current_step, cumulative_time, self.jobs[i][current_step]['avg_time'],
                           self.jobs[i][current_step]['avg_mem'], self.jobs[i][current_step]['avg_cpu'],
                           self.jobs[i][current_step]['commands'], prev_exit)

                next_jobs.append(element)
                # print i, j, self.jobs[i][j]['avg_time']

        return sorted(next_jobs, key=itemgetter(2), reverse=True)

    def putNextJobsOnQueue(self, jobs=None):
        print 'put next jobs on queue', '\n'
        for j in jobs:
            print j[0], j[1]

        for job in jobs:

            if job[0] in self.started_jobs or not self.checkIfEnoughMemory(job[4]) or not self.checkIfEnoughCPU(job[5]):

                resource_not_available = []
                if job[0] in self.started_jobs:
                    resource_not_available.append('prev step not finished')
                if not self.checkIfEnoughMemory(job[4]):
                    resource_not_available.append('not enough memory')
                if not self.checkIfEnoughCPU(job[5]):
                    resource_not_available.append('not enough cpu')

                print 'skipping job', job[0], job[1], 'because ', ','.join(resource_not_available)

                continue

            with self.started_jobs_lock:
                self.started_jobs.append(job[0])
                self.availableMemory = self.availableMemory - job[4]
                self.availableCPU = self.availableCPU - job[5]
                thread_job = workerThread(process_relval_workflow_step, job)
                #thread_job = workerThread(relval_test_process, job)
                '''
                callbacks calls
                '''
                if job[0] not in self.results:
                    # its the first step of the wf, execute one time pre wf callback
                    self._workflowIsStarting(job[0], self.jobs_result_folders[job[0]])
                # and once per step
                self._stepIsStarting(job[0], job[1], self.jobs_result_folders[job[0]])
                self.toProcessQueue.put(thread_job)

            self._removeJobFromWorkflow(job[0], job[1])
            # print self.jobs

        print 'jobs putted on queue'

    '''
    finishing jobs after process
    '''

    def getFinishedJobs(self):

        while True:

            print 'get finished jobs', '\n'
            # print 'jobs from finished jobs', '\n', self.jobs
            finishedJob = self.processedQueue.get()  # gets the return value from thread function, i.e. wf step result
            self.finishJob(finishedJob)
            # print finishedJob['id']
            self.processedQueue.task_done()
            self.counter.release()  # release the lock for each finished job, putJobsOnQueue retries to put new jobs

            print 'finished get finished jobs for ', finishedJob['id'], '\n'

            if not self.jobs and not self.started_jobs:
                print 'breaking get finished jobs'
                break

    def finishJob(self, job=None):
        print 'finish', job['id'], job['step'], job['exit_code'], job['mem'], job['cpu']
        # callback call when step is finished
        self._stepIsFinishing(job['id'], job['step'], self.jobs_result_folders[job['id']])
        self._insertRecordInResults(job)
        # insert the record before removing the job since it might remove the entire job

        with self.started_jobs_lock:
            self.availableMemory += job['mem']
            self.availableCPU += job['cpu']
            self.started_jobs.remove(job['id'])
            print 'job removed: ', job['id']

        # finish the workflow if the step was the last

        with self.jobs_lock:
            if not job['id'] in self.jobs:
                print 'finalize wf:', job['id']
                with self.results_lock:
                    self.results[job['id']]['finishing_exit'] = 'finished'
                    job_results = self.results[job['id']]
                    current_job_folder = self.jobs_result_folders[job['id']]
                    # callback call when the entire workflow is finished
                    self._workflowIsFinishing(job['id'], current_job_folder, job_results)

    '''
    protected methods
    '''

    def _removeJobFromWorkflow(self, jobID=None, stepID=None):
        with self.jobs_lock:
            if jobID in self.jobs and stepID in self.jobs[jobID]:
                if len(self.jobs[jobID]) == 1:
                    self._removeWorkflow(jobID)
                else:
                    del self.jobs[jobID][stepID]

    def _removeWorkflow(self, wf_id=None):
        if wf_id in self.jobs:
            del self.jobs[wf_id]

    def _insertRecordInResults(self, result=None):

        with self.results_lock:
            if not result['id'] in self.results:
                self.results[result['id']] = {}

            self.results[result['id']][result['step']] = {'exit_code': result['exit_code'], 'stdout': result['stdout'],
                                                          'stderr': result['stderr'], 'start_time': result['startTime'],
                                                          'end_time': result['endTime'],
                                                          'exec_time': result['endTime'] - result['startTime']}

    def writeResultsInFile(self, filen=None):
        with self.results_lock:
            with open(filen, 'w') as results_file:
                results_file.write(json.dumps(self.results, indent=1, sort_keys=True))

    '''
    callback methods to be called 
    '''

    def _workflowIsStarting(self, *args):
        #print 'wf is starting'
        if self.workflowIsStarting:
            self.workflowIsStarting(*args)

    def _workflowIsFinishing(self, *args):
        #print 'wf is finishing, job id: ', args[0]
        if self.workflowIsFinishing:
            self.workflowIsFinishing(*args)

    def _stepIsStarting(self, *args):
        #print 'step is starting: ',
        if self.stepIsStarting:
            self.stepIsStarting(*args)

    def _stepIsFinishing(self, *args):
        print args
        if self.stepIsFinishing:
            self.stepIsFinishing(*args)


''' 
the task list 
'''

if __name__ == "__main__":
    jobs_result = {
        "finishing_exit": "finished",
        "step1": {
            "exit_code": 0,
            "stderr": None,
            "stdout": ""
        },
        "step2": {
            "exit_code": 0,
            "stderr": None,
            "stdout": ""
        },
        "step3": {
            "exit_code": 0,
            "stderr": None,
            "stdout": ""
        }
    }

    keys_list = sorted(jobs_result, reverse=False)

    # given_wf_folder = 'resources/finished_wf_folders/matrix/2.0_ProdTTbar+ProdTTbar+DIGIPROD1+RECOPROD1'
    given_wf_folder = 'resources/finished_wf_folders/matrix/1.0_ProdMinBias+ProdMinBias+DIGIPROD1+RECOPROD1'

    writeWorkflowLog(given_wf_folder, jobs_result)

    getWorkflowDuration(given_wf_folder)

    pass
