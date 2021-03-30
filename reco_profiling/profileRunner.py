#!/usr/bin/env python3
#Profile runner for step3 and step4
import subprocess
import glob
import sys
import os
import shutil

def prepareMatrixWF(workflow_number, num_events):
    cmd = [
         "runTheMatrix.py",
         "-w",
         "upgrade",
         "-l",
         workflow_number,
         "--command",
         "\"-n {}\"".format(num_events),
         "--dryRun"
    ]
    out = subprocess.check_output(cmd)

def parseCmdLog(filename):
    cmsdriver_lines = []
    with open(filename) as fi:
        for line in fi.readlines():
            line = line.strip()
            if line.strip().startswith("cmsDriver"):
                cmsdriver_lines.append(stripPipe(line))
    return cmsdriver_lines

def stripPipe(cmsdriver_line):
    return cmsdriver_line[:cmsdriver_line.index(">")]

def getWFDir(workflow_number):
    dirs = list(glob.glob("{}_*".format(workflow_number)))
    if len(dirs) != 1:
        return None
    return dirs[0]

def wrapInRetry(cmd):
    s = """n=0
until [ "$n" -ge 5 ]
do
   echo "attempt $n"
   {} && break
   n=$((n+1))
done""".format(cmd)
    return s

def echoBefore(cmd, msg):
    s = """
echo "{}"
{}
""".format(msg, cmd)
    return s

def configureProfilingSteps(cmsdriver_lines, num_events):
    assert("step1" in cmsdriver_lines[0])
    assert("step2" in cmsdriver_lines[1])
    assert("step3" in cmsdriver_lines[2])
    assert("step4" in cmsdriver_lines[3])

    cmsdriver_lines[0] = cmsdriver_lines[0] + "&> step1.log"
    cmsdriver_lines[1] = cmsdriver_lines[1] + "&> step2.log"

    step3 = cmsdriver_lines[2]
    step3_tmi = step3 + " --customise=Validation/Performance/TimeMemoryInfo.py &> step3_TimeMemoryInfo.log"
    step3_ft = step3 + " --customise HLTrigger/Timer/FastTimer.customise_timer_service_singlejob --customise_commands \"process.FastTimerService.writeJSONSummary=True;process.FastTimerService.jsonFileName=\\\"step3_circles.json\\\"\" &> step3_FastTimerService.log"
    step3_ig = step3 + "--customise Validation/Performance/IgProfInfo.customise --no_exec --python_filename step3_igprof.py &> step3_igprof_conf.txt"

    igprof_s3_pp = wrapInRetry("igprof -d -pp -z -o step3_igprofCPU.gz -t cmsRun cmsRun step3_igprof.py &> step3_igprof_cpu.txt")
    igprof_s3_mp = wrapInRetry("igprof -d -mp -z -o step3_igprofMEM.gz -t cmsRunGlibC cmsRunGlibC step3_igprof.py &> step3_igprof_mem.txt")

    step4 = cmsdriver_lines[3]
    step4_tmi = step4 + " --customise=Validation/Performance/TimeMemoryInfo.py &> step4_TimeMemoryInfo.log"
    step4_ft = step4 + " --customise HLTrigger/Timer/FastTimer.customise_timer_service_singlejob --customise_commands \"process.FastTimerService.writeJSONSummary=True;process.FastTimerService.jsonFileName=\\\"step4_circles.json\\\"\" &> step4_FastTimerService.log"
    step4_ig = step4 + "--customise Validation/Performance/IgProfInfo.customise --no_exec --python_filename step4_igprof.py &> step4_igprof_conf.txt"

    igprof_s4_pp = wrapInRetry("igprof -d -pp -z -o step4_igprofCPU.gz -t cmsRun cmsRun step4_igprof.py &> step4_igprof_cpu.txt")
    igprof_s4_mp = wrapInRetry("igprof -d -mp -z -o step4_igprofMEM.gz -t cmsRunGlibC cmsRunGlibC step4_igprof.py &> step4_igprof_mem.txt")

    new_cmdlist = (cmsdriver_lines[:2] +
        [echoBefore(step3_tmi, "step3 TimeMemoryInfo"),
        echoBefore(step3_ft, "step3 FastTimer"),
        echoBefore(step3_ig, "step3 IgProf conf"),
        echoBefore(igprof_s3_pp, "step3 IgProf pp"),
        "mv IgProf.1.gz step3_igprofCPU.1.gz",
        "mv IgProf.{nev}.gz step3_igprofCPU.{nev}.gz".format(nev=int(num_events/2)),
        "mv IgProf.{nev}.gz step3_igprofCPU.{nev}.gz".format(nev=int(num_events-1)),
        echoBefore(igprof_s3_mp, "step3 IgProf mp"),
        "mv IgProf.1.gz step3_igprofMEM.1.gz",
        "mv IgProf.{nev}.gz step3_igprofMEM.{nev}.gz".format(nev=int(num_events/2)),
        "mv IgProf.{nev}.gz step3_igprofMEM.{nev}.gz".format(nev=int(num_events-1)),
        ] +
        [echoBefore(step4_tmi, "step4 TimeMemoryInfo"),
        echoBefore(step4_ft, "step4 FastTimer"),
        echoBefore(step4_ig, "step4 IgProf conf"),
        echoBefore(igprof_s4_pp, "step4 IgProf pp"),
        "mv IgProf.1.gz step4_igprofCPU.1.gz",
        "mv IgProf.{nev}.gz step4_igprofCPU.{nev}.gz".format(nev=int(num_events/2)),
        "mv IgProf.{nev}.gz step4_igprofCPU.{nev}.gz".format(nev=int(num_events-1)),
        echoBefore(igprof_s4_mp, "step4 IgProf mp"),
        "mv IgProf.1.gz step4_igprofMEM.1.gz",
        "mv IgProf.{nev}.gz step4_igprofMEM.{nev}.gz".format(nev=int(num_events/2)),
        "mv IgProf.{nev}.gz step4_igprofMEM.{nev}.gz".format(nev=int(num_events-1)),
        ])

    return new_cmdlist

def writeProfilingScript(wfdir, runscript, cmdlist):
    runscript_path = "{}/{}".format(wfdir, runscript)
    with open(runscript_path, "w") as fi:
        fi.write("#!/bin/bash\n")
        fi.write("ulimit -a\n")

        #abort on error
        fi.write("set -e\n")
        
        #print commands verbosely
        fi.write("set -x\n")
        for cmd in cmdlist:
            fi.write(cmd + '\n')

    return

def runProfiling(wfdir, runscript):
    os.chdir(wfdir)
    os.system("chmod +x {}".format(runscript))
    os.system("bash {}".format(runscript))
    os.chdir("..")

def copyProfilingOutputs(wfdir, out_dir, num_events):
    for output in [
        "step1.root",
        "step2.root",
        "step3.root",
        "step4.root",
        "step1.log",
        "step2.log",
        "step3_TimeMemoryInfo.log",
        "step3_circles.json",
        "step3_igprofCPU.gz",
        "step3_igprofMEM.1.gz",
        "step3_igprofMEM.{}.gz".format(int(num_events-1)),
        "step3_igprofMEM.{}.gz".format(int(num_events/2)),
        "step4_TimeMemoryInfo.log",
        "step4_circles.json",
        "step4_igprofCPU.gz",
        "step4_igprofMEM.1.gz",
        "step4_igprofMEM.{}.gz".format(int(num_events-1)),
        "step4_igprofMEM.{}.gz".format(int(num_events/2)),
        ]:
        path = "{}/{}".format(wfdir, output)

        #check that all outputs exists and are of nonzero size
        if os.path.isfile(path) and os.stat(path).st_size > 0:
            print("copying {} to {}".format(path, out_dir))
            shutil.copy(path, out_dir)
        else:
            raise Exception("Output {} not found or is broken".format(path))
    return

def main(wf, num_events, out_dir):
    wfdir = getWFDir(wf)
    
    if not (wfdir is None):
        print("Output directory {} exists, aborting".format(wfdir))
        sys.exit(1)

    prepareMatrixWF(wf, num_events)
    wfdir = getWFDir(wf)
    cmsdriver_lines = parseCmdLog("{}/cmdLog".format(wfdir))
    new_cmdlist = configureProfilingSteps(cmsdriver_lines, num_events)

    runscript = "cmdLog_profiling.sh"
    writeProfilingScript(wfdir, runscript, new_cmdlist)
    runProfiling(wfdir, runscript)
    copyProfilingOutputs(wfdir, out_dir, num_events)

def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=str, default="23434.21", help="The workflow to use for profiling")
    parser.add_argument("--num-events", type=int, default=100, help="Number of events to use")
    parser.add_argument("--out-dir", type=str, help="The output directory where to copy the profiling results", required=True)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse_args()
    
    os.makedirs(args.out_dir)

    main(args.workflow, args.num_events, args.out_dir)


