__author__ = 'mrodozov@cern.ch'
'''

'''

from threading import Thread
import Queue
from JobsManager import workerThread
from time import sleep

def dummyTimeWastingTask(duration=10):
    while duration:
        print 'ETA: ', duration
        duration = duration -1
        sleep(1)
    return 'Exit code and whatever'

class JobsProcessor(Thread):

    def __init__(self, to_process_queue=None, processed_queue=None):
        super(JobsProcessor, self).__init__()
        self._toProcessQueue = to_process_queue
        self._processedQueue = processed_queue
        self.allJobs = None
        self.allJobs_lock = None
        self.startProcess = Thread(target=self.startTasks)
        #self.finishProcess = Thread(target=self.finishTasks)
    
    def startTasks(self):
        while True:

            with self.allJobs_lock:
                if not self.allJobs and self._toProcessQueue.empty():
                    print 'finished get QUEUE'
                    break

            task = self._toProcessQueue.get()
            task.resultQueue = self._processedQueue
            task.start()
            #print 'processing task ', task.name
            self._toProcessQueue.task_done()
            #self.finish
            print 'size of jobs:', len(self.allJobs), "\n"
                #, self.allJobs

    def run(self):

        self.startProcess.start()
        self.startProcess.join()
        #print ''

if __name__ == "__main__":

    toProcessQueue = Queue.Queue()
    processedTasksQueue = Queue.Queue()

    dthread1 = workerThread(dummyTimeWastingTask, 10)
    dthread1.name = 'first'
    dthread2 = workerThread(dummyTimeWastingTask, 15)
    dthread2.name = 'second'
    dthread3 = workerThread(dummyTimeWastingTask, 20)
    dthread3.name = 'third'

    toProcessQueue.put(dthread1)
    toProcessQueue.put(dthread2)
    toProcessQueue.put(dthread3)

    tp = JobsProcessor(toProcessQueue, processedTasksQueue)
    tp.start()
    tp.join()
