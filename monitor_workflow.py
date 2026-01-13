#!/usr/bin/env python3
from os import system, getpid
from sys import argv, exit
import psutil
from threading import Thread
import subprocess
from json import dump
from time import sleep, time

try:
    from time import monotonic
except ImportError:
    monotonic = time

SAMPLE_INTERVAL = 1.0
cpu_times = {}
job = {"exit_code": 0, "command": "true"}


def run_job(job):
    job["exit_code"] = subprocess.call(job["command"])


def update_stats(proc):
    global cpu_times
    stats = {
        "rss": 0,
        "vms": 0,
        "shared": 0,
        "data": 0,
        "uss": 0,
        "pss": 0,
        "num_fds": 0,
        "num_threads": 0,
        "processes": 0,
        "cpu": 0,
    }
    try:
        children = proc.children(recursive=True)
    except:
        return stats
    clds = len(children)
    if clds == 0:
        return stats
    stats["processes"] = clds
    sleep(SAMPLE_INTERVAL)
    new_cpu_times = {}
    for cld in children:
        pid = cld.pid
        try:
            current_time = monotonic()
            new_cpu = cld.cpu_times()
            old_cpu, last_time = cpu_times.get(pid, (None, None))
            cpu_delta = 0
            elapsed = 0
            if old_cpu:
                delta = (new_cpu.user - old_cpu.user) + (new_cpu.system - old_cpu.system)
                elapsed = current_time - last_time
            else:
                delta = new_cpu.user + new_cpu.system
                elapsed = time() - cld.create_time()
            if elapsed >= 0.1:
                stats["cpu"] += int((delta / elapsed) * 100.0)
            new_cpu_times[pid] = (new_cpu, current_time)
        except:
            continue
        try:
            stats["num_fds"] += cld.num_fds()
            stats["num_threads"] += cld.num_threads()
            mem = None
            try:
                mem = cld.memory_full_info()
                for a in ["uss", "pss"]:
                    stats[a] += getattr(mem, a)
            except:
                try:
                    mem = cld.memory_info()
                except:
                    mem = cld.memory_info_ex()
            for a in ["rss", "vms", "shared", "data"]:
                stats[a] += getattr(mem, a)
        except:
            pass
    cpu_times = new_cpu_times
    return stats


def monitor(stop):
    stime = int(time())
    p = psutil.Process(getpid())
    cmdline = " ".join(p.parent().cmdline())
    if "cmsDriver.py " in cmdline:
        cmdargs = cmdline.split("cmsDriver.py ", 1)[1].strip()
        step = None
        if cmdargs.startswith("step"):
            step = cmdargs.split(" ")[0]
        elif " --fileout " in cmdargs:
            step = (
                cmdargs.split(" --fileout ", 1)[1]
                .strip()
                .split(" ")[0]
                .replace("file:", "")
                .replace(".root", "")
            )
        if not "step" in step:
            step = "step1"
    else:
        step = stime
    data = []
    sleep_time = 1
    while not stop():
        try:
            stats = update_stats(p)
            if stats["processes"] == 0:
                break
            stats["time"] = int(time() - stime)
            data.append(stats)
        except:
            pass
    stat_file = open("wf_stats-%s.json" % step, "w")
    dump(data, stat_file)
    stat_file.close()
    return


stop_monitoring = False
job["command"] = argv[1:]
job_thd = Thread(target=run_job, args=(job,))
mon_thd = Thread(target=monitor, args=(lambda: stop_monitoring,))
job_thd.start()
sleep(1)
mon_thd.start()
job_thd.join()
stop_monitoring = True
mon_thd.join()
exit(job["exit_code"])
