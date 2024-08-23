#! /usr/bin/env python

from __future__ import print_function, division

import glob
import psutil
import sys
import time

from psutil import AccessDenied, NoSuchProcess

time.sleep(60)

testPid = 0
while not testPid:
    print("TESTWATCH: Polling")
    for process in psutil.process_iter():
        try:
            if (
                "python" in process.cmdline()[0]
                and "setup.py" in process.cmdline()[1]
                and process.cmdline()[2] == "test"
            ):
                testPid = process.pid
                print("TESTWATCH: Found pid %s" % testPid)
        except TypeError:
            if (
                "python" in process.cmdline[0]
                and "setup.py" in process.cmdline[1]
                and process.cmdline[2] == "test"
            ):
                testPid = process.pid
                print("TESTWATCH: Found pid %s" % testPid)
        except (IndexError, AccessDenied, NoSuchProcess):
            pass
    time.sleep(10)

noXMLTime = time.time()
while True:
    foundXML = False
    try:
        time.sleep(10)
        process = psutil.Process(testPid)
        try:
            userCPU = process.cpu_times().user
        except AttributeError:
            userCPU = process.get_cpu_times()[0]
        for xunitFile in glob.iglob("nosetests*.xml"):
            foundXML = True

        if not foundXML:
            noXMLTime = time.time()
        else:
            xmlAge = time.time() - noXMLTime
            if xmlAge > 450:
                print("TESTWATCH: XML file is %s seconds old. Killing process" % xmlAge)
                process.terminate()
                time.sleep(10)
                process.kill()
    except:
        sys.exit(0)

sys.exit(0)
