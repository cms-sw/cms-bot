#!/usr/bin/env python3
#Profile runner for reco releases
#maintained by the CMS reco group
import subprocess
import glob
import sys
import os
import shutil

workflow_configs = {
    #Run3 workflow
    "11834.21": {
        "num_events": 400,
        "steps": {
            "step3": {
                "TimeMemoryInfo": True,
                "FastTimer": True,
                "igprof": True,
            },
            "step4": {
                "TimeMemoryInfo": True,
                "FastTimer": True,
                "igprof": True,
            },
            "step5": {
                "TimeMemoryInfo": True,
                "FastTimer": True,
                "igprof": True,
            },
         },
        "nThreads": 1,
        "matrix": "upgrade"
    },
    #Phase2 workflow used in mid-2021
    "23434.21": {
        "num_events": 100,
        "steps": {
            "step3": {
                "TimeMemoryInfo": True,
                "FastTimer": True,
                "igprof": True,
            },
            "step4": {
                "TimeMemoryInfo": True,
                "FastTimer": True,
                "igprof": True,
            },
            "step5": {
                "TimeMemoryInfo": True,
                "FastTimer": True,
                "igprof": True,
            },
         },
        "nThreads": 1,
        "matrix": "upgrade"
    },
    #Phase2 workflow used in late-2021
    "34834.21": {
        "num_events": 100,
        "steps": {
            "step3": {
                "TimeMemoryInfo": True,
                "FastTimer": True,
                "igprof": True,
            },
            "step4": {
                "TimeMemoryInfo": True,
                "FastTimer": True,
                "igprof": True,
            },
         },
        "nThreads": 1,
        "matrix": "upgrade"
    } ,
    #8-thread T0-like promptreco workflow
    "136.889": {
        "num_events": 100,
        "steps": {
            "step3": {
                "TimeMemoryInfo": True,
                "FastTimer": False,
                "igprof": False,
            },
         },
        "nThreads": 8,
        "matrix": "standard"
    } 
}

def fixIgProfExe():
    ver = os.environ["CMSSW_VERSION"]

    #affected by https://github.com/cms-sw/cmssw/issues/33297
    if ver.startswith("CMSSW_11_3_0_pre5") or ver.startswith("CMSSW_11_3_0_pre6"):
        runner_path = os.path.dirname(os.path.realpath(__file__))
        return os.path.join(runner_path, "igprof-fixed.sh")

    return "igprof"

#Prepare cmdLog and execute the workflow steps to get e.g. DAS entries, but call cmsRun with --no_exec
def prepareMatrixWF(workflow_number, num_events, matrix="upgrade", nthreads=1):
    cmd = [
         "runTheMatrix.py",
         "-w",
         matrix,
         "-l",
         str(workflow_number),
         "--command=\"--no_exec\"",
         "--ibeos",
         "--nThreads",
         str(nthreads),
    ]
    cmd = " ".join(cmd)
    os.system(cmd)

#extracts the cmsdriver lines from the cmdLog
def parseCmdLog(filename):
    cmsdriver_lines = []
    with open(filename) as fi:
        for line in fi.readlines():
            line = line.strip()
            if line.strip().startswith("cmsDriver"):
                line = line.replace("--no_exec", "")
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

def prepTimeMemoryInfo(cmd, istep):
    cmd_tmi = cmd + " --customise=Validation/Performance/TimeMemoryInfo.py &> step{}_TimeMemoryInfo.log".format(istep)
    return cmd_tmi

def prepFastTimer(cmd, istep):
    cmd_ft = cmd + " --customise HLTrigger/Timer/FastTimer.customise_timer_service_singlejob --customise_commands \"process.FastTimerService.writeJSONSummary=True;process.FastTimerService.jsonFileName=\\\"step{istep}_circles.json\\\"\" &> step{istep}_FastTimerService.log".format(istep=istep)
    return cmd_ft

def prepIgprof(cmd, istep):
    cmd_ig = cmd + " --customise Validation/Performance/IgProfInfo.customise --no_exec --python_filename step{istep}_igprof.py &> step{istep}_igprof_conf.txt".format(istep=istep)
    return cmd_ig 

def configureProfilingSteps(cmsdriver_lines, num_events, steps_config):
    igprof_exe = fixIgProfExe()

    steps = {}
    for line in cmsdriver_lines:
        spl = line.split()[1]
        #step1 has the format `cmsDriver.py fragment`, otherwise it's `cmsDriver.py stepN`
        if "step" in spl:
            istep = int(spl.replace("step", ""))
        else:
            istep = 1
        steps[istep] = line + " -n {num_events} --suffix \"-j step{istep}_JobReport.xml\"".format(istep=istep, num_events=num_events)

    steps_to_run = list(sorted(steps.keys()))
    outfiles = [
        "step{}_JobReport.xml".format(istep) for istep in steps_to_run
    ]
    outfiles += [
        "step{}.root".format(istep) for istep in steps_to_run
    ]
    outfiles += [
        "step{}.log".format(istep) for istep in steps_to_run
    ]

    #First run all the steps without any special options 
    new_cmdlist = [steps[istep]+"&>step{istep}.log".format(istep=istep) for istep in steps_to_run]

    igprof_commands = []
    for step_name in steps_config.keys():
        istep = int(step_name.replace("step", ""))
        step = steps[istep]

        #strip the JobReport from the step command
        step = step[:step.index("--suffix")-1]

        if steps_config[step_name]["TimeMemoryInfo"]:
            step_tmi = prepTimeMemoryInfo(step, istep)
            outfiles += ["step{}_TimeMemoryInfo.log".format(istep)]
            new_cmdlist += [
                echoBefore(step_tmi, "step{istep} TimeMemoryInfo".format(istep=istep))
            ]
        if steps_config[step_name]["FastTimer"]:
            step_ft = prepFastTimer(step, istep)
            outfiles += ["step{}_FastTimerService.log".format(istep), "step{}_circles.json".format(istep)]
            new_cmdlist += [
                echoBefore(step_ft, "step{istep} FastTimer".format(istep=istep)),
            ]
        if steps_config[step_name]["igprof"]:
            step_ig = prepIgprof(step, istep)
            new_cmdlist += [
                echoBefore(step_ig, "step{istep} IgProf conf".format(istep=istep))
            ]
            
            igprof_pp = wrapInRetry(igprof_exe + " -d -pp -z -o step{istep}_igprofCPU.gz -t cmsRun cmsRun step{istep}_igprof.py &> step{istep}_igprof_cpu.txt".format(istep=istep))
            igprof_mp = wrapInRetry(igprof_exe + " -d -mp -z -o step{istep}_igprofMEM.gz -t cmsRunGlibC cmsRunGlibC step{istep}_igprof.py &> step{istep}_igprof_mem.txt".format(istep=istep))
            outfiles += [
                "step{istep}_igprof_cpu.txt".format(istep=istep), 
                "step{istep}_igprof_mem.txt".format(istep=istep)
            ]
            
            igprof_commands += [
                echoBefore(igprof_pp, "step{istep} IgProf pp".format(istep=istep)),
                "mv IgProf.1.gz step{istep}_igprofCPU.1.gz".format(istep=istep),
                "mv IgProf.{nev}.gz step{istep}_igprofCPU.{nev}.gz".format(nev=int(num_events/2), istep=istep),
                "mv IgProf.{nev}.gz step{istep}_igprofCPU.{nev}.gz".format(nev=int(num_events-1), istep=istep),
                echoBefore(igprof_mp, "step{istep} IgProf mp".format(istep=istep)),
                "mv IgProf.1.gz step{istep}_igprofMEM.1.gz".format(istep=istep),
                "mv IgProf.{nev}.gz step{istep}_igprofMEM.{nev}.gz".format(nev=int(num_events/2), istep=istep),
                "mv IgProf.{nev}.gz step{istep}_igprofMEM.{nev}.gz".format(nev=int(num_events-1), istep=istep),
            ]

            outfiles += [
                "step{istep}_igprofCPU.{nev}.gz".format(istep=istep, nev=nev) for nev in [1,int(num_events/2), int(num_events-1)]
            ]
            outfiles += [
                "step{istep}_igprofMEM.{nev}.gz".format(istep=istep, nev=nev) for nev in [1,int(num_events/2), int(num_events-1)]
            ]
            outfiles += [
                "step{istep}_igprofCPU.gz".format(istep=istep)
            ]

    new_cmdlist = new_cmdlist + igprof_commands

    return new_cmdlist, outfiles

def writeProfilingScript(wfdir, runscript, cmdlist):
    runscript_path = "{}/{}".format(wfdir, runscript)
    with open(runscript_path, "w") as fi:
        fi.write("#!/bin/sh\n")

        #this is required for igprof
        fi.write("ulimit -a\n")

        #don't abort on error
        #fi.write("set -e\n")
        
        #print commands verbosely
        fi.write("set -x\n")

        fi.write("\n")
        for cmd in cmdlist:
            fi.write(cmd + '\n')

    return

def runProfiling(wfdir, runscript):
    os.chdir(wfdir)
    os.system("chmod +x {}".format(runscript))
    os.system("bash {}".format(runscript))
    os.chdir("..")

def copyProfilingOutputs(wfdir, out_dir, outfiles):
    for output in outfiles:
        path = "{}/{}".format(wfdir, output)

        #check that all outputs exists and are of nonzero size
        if os.path.isfile(path) and os.stat(path).st_size > 0:
            print("copying {} to {}".format(path, out_dir))
            shutil.copy(path, out_dir)
        else:
            print("ERROR: Output {} not found or is broken, skipping".format(path))
    return

def main(wf, num_events, out_dir):
    wfdir = getWFDir(wf)
    
    if not (wfdir is None):
        print("Output directory {} exists, aborting".format(wfdir))
        sys.exit(1)

    prepareMatrixWF(wf, num_events, matrix=workflow_configs[wf]["matrix"], nthreads=workflow_configs[wf]["nThreads"])
    wfdir = getWFDir(wf)
    cmsdriver_lines = parseCmdLog("{}/cmdLog".format(wfdir))
    new_cmdlist, outfiles = configureProfilingSteps(cmsdriver_lines, num_events, workflow_configs[wf]["steps"])

    runscript = "cmdLog_profiling.sh"
    outfiles += ["cmdLog_profiling.sh"]
    writeProfilingScript(wfdir, runscript, new_cmdlist)
    runProfiling(wfdir, runscript)
    copyProfilingOutputs(wfdir, out_dir, outfiles)

def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=str, default="34834.21", help="The workflow to use for profiling")
    parser.add_argument("--num-events", type=int, default=-1, help="Number of events to use, -1 to use the default")
    parser.add_argument("--out-dir", type=str, help="The output directory where to copy the profiling results", required=True)
    args = parser.parse_args()
    if args.num_events==-1:
        args.num_events = workflow_configs[args.workflow]["num_events"]
    return args

if __name__ == "__main__":
    args = parse_args()
    
    os.makedirs(args.out_dir)

    main(args.workflow, args.num_events, args.out_dir)
