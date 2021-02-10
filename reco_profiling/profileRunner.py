#!/usr/bin/env python3
#Profile runner for step3 and step4
import subprocess
import glob
import sys
import os

def prepareMatrixWF(workflow_number, num_events):
	cmd = [
	 	"runTheMatrix.py",
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

def configureProfilingSteps(cmsdriver_lines):
	assert(len(cmsdriver_lines) == 4)
	assert("step1" in cmsdriver_lines[0])
	assert("step2" in cmsdriver_lines[1])
	assert("step3" in cmsdriver_lines[2])
	assert("step4" in cmsdriver_lines[3])

	cmsdriver_lines[0] = cmsdriver_lines[0] + "&> step1.log"
	cmsdriver_lines[1] = cmsdriver_lines[1] + "&> step2.log"

	step3 = cmsdriver_lines[2]
	step3_tmi = step3 + " --customise=Validation/Performance/TimeMemoryInfo.py &> step3_TimeMemoryInfo.log"
	step3_ft = step3 + " --customise HLTrigger/Timer/FastTimer.customise_timer_service_singlejob --customise_commands \"process.FastTimerService.writeJSONSummary=True;process.FastTimerService.jsonFileName=\\\"step3_circles.json\\\"\" &> step3_FastTimerService.log"
	step3_ig = step3 + "--customise Validation/Performance/IgProfInfo.customise --no_exec --python_filename step3_igprof.py"

	igprof_s3_pp = "igprof -d -pp -z -o step3_igprofCPU.gz -t cmsRun cmsRun step3_igprof.py &> step3_igprof_cpu.txt"
	igprof_s3_mp = "igprof -d -mp -z -o step3_igprofMEM.gz -t cmsRunGlibC cmsRunGlibC step3_igprof.py &> step3_igprof_mem.txt"

	step4 = cmsdriver_lines[3]
	step4_tmi = step4 + " --customise=Validation/Performance/TimeMemoryInfo.py &> step4_TimeMemoryInfo.log"
	step4_ft = step4 + " --customise HLTrigger/Timer/FastTimer.customise_timer_service_singlejob --customise_commands \"process.FastTimerService.writeJSONSummary=True;process.FastTimerService.jsonFileName=\\\"step4_circles.json\\\"\" &> step4_FastTimerService.log"
	step4_ig = step4 + "--customise Validation/Performance/IgProfInfo.customise --no_exec --python_filename step4_igprof.py"

	igprof_s4_pp = "igprof -d -pp -z -o step4_igprofCPU.gz -t cmsRun cmsRun step4_igprof.py &> step4_igprof_cpu.txt"
	igprof_s4_mp = "igprof -d -mp -z -o step4_igprofMEM.gz -t cmsRunGlibC cmsRunGlibC step4_igprof.py &> step4_igprof_mem.txt"

	new_cmdlist = (cmsdriver_lines[:2] +
		[step3_tmi, step3_ft, step3_ig, igprof_s3_pp, igprof_s3_mp] +
		[step4_tmi, step4_ft, step4_ig, igprof_s4_pp, igprof_s4_mp])

	return new_cmdlist

def writeProfilingScript(wfdir, runscript, cmdlist):
	runscript_path = "{}/{}".format(wfdir, runscript)
	with open(runscript_path, "w") as fi:
		fi.write("#!/bin/bash\n")

		#abort on error
		fi.write("set -e\n")
		for cmd in cmdlist:
			fi.write(cmd + '\n')

	return

def runProfiling(wfdir, runscript):
	os.chdir(wfdir)
	os.system("chmod +x {}".format(runscript))
	os.system("bash {}".format(runscript))
	os.chdir("..")

def validateProfilingOutputs(wfdir):
	ret = {}

	for output in [
		"step3_TimeMemoryInfo.log",
		"step3_circles.json",
		"step3_igprofCPU.gz",
		"step3_igprofMEM.gz",
		"step4_TimeMemoryInfo.log",
		"step4_circles.json",
		"step4_igprofCPU.gz",
		"step4_igprofMEM.gz",
		]:
		path = "{}/{}".format(wfdir, output)

		#check that all outputs exists and are of nonzero size
		if os.path.isfile(path) and os.stat(path).st_size > 0:
			ret[output.split(".")[0]] = path
		else:
			raise Exception("Output {} not found or is broken".format(path))

	return ret

def main(wf, num_events):
	wfdir = getWFDir(wf)
	
	if not (wfdir is None):
		print("Output directory {} exists, aborting".format(wfdir))
		sys.exit(1)

	prepareMatrixWF(wf, num_events)
	wfdir = getWFDir(wf)
	cmsdriver_lines = parseCmdLog("{}/cmdLog".format(wfdir))
	new_cmdlist = configureProfilingSteps(cmsdriver_lines)

	runscript = "cmdLog_profiling.sh"
	writeProfilingScript(wfdir, runscript, new_cmdlist)
	runProfiling(wfdir, runscript)

	ret = validateProfilingOutputs(wfdir)
	print(ret)

def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=str, default="23434.21", help="The workflow to use for profiling")
    parser.add_argument("--num-events", type=int, default=100, help="Number of events to use")
    args = parser.parse_args()
    return args

if __name__ == "__main__":
	args = parse_args()
	main(args.workflow, args.num_events)