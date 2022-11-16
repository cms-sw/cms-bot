#!/usr/bin/env python3
import glob, os, sys


def compile_lib():
    lib_dir = 'validate_lib'
    if not os.path.isfile(f'{lib_dir}/validate_C.so'):
        os.makedirs(lib_dir, exist_ok=True)
        if not 'VALIDATE_C_SCRIPT' in os.environ or not os.environ['VALIDATE_C_SCRIPT']:
            os.environ['VALIDATE_C_SCRIPT'] = os.path.join(os.environ['HOME'],'tools','validate.C')
        os.system(f"cp $VALIDATE_C_SCRIPT {lib_dir}/validate.C")
        command = f'cd {lib_dir};'+'echo -e "gSystem->Load(\\"libFWCoreFWLite.so\\");AutoLibraryLoader::enable();FWLiteEnabler::enable();\n .L validate.C+ \n .qqqqqq\" | root -l -b'
        print(f"compiling library with {command}")
        os.system( command )
    os.environ['LD_LIBRARY_PATH'] = ':'.join([os.path.join(os.getcwd(),'validate_lib'),os.environ['LD_LIBRARY_PATH']])
    return os.path.isfile(f'{lib_dir}/validate_C.so')

def run_comparison(fileName, base_dir, ref_dir, processName, output_dir):
    base_file=os.path.join(base_dir,fileName)
    ref_file=os.path.join(ref_dir,fileName)
    logFile=os.path.join(output_dir,fileName.replace('.root','.log'))
    os.makedirs(output_dir ,exist_ok=True)
    what_is_called_step_in_the_script = output_dir
    command = f'echo -e "gSystem->Load(\\"libFWCoreFWLite.so\\");AutoLibraryLoader::enable();FWLiteEnabler::enable();gSystem->Load(\\"validate_C.so\\");validate(\\"{what_is_called_step_in_the_script}\\",\\"{base_file}\\",\\"{ref_file}\\",\\"{processName}\\");\n.qqqqqq" | root -l -b >& {logFile}'
    #print(f"running comparison with {command}")
    print(f"log of comparing {fileName} process {processName} from {base_dir} and {ref_dir} into {output_dir} shown in {logFile}")
    c=os.system( command )
    #print(f"comparison exit signal is {c}")
    #if c!=0: return False
    return True

def file_processes(fileName):
    max_proc=20
    prov_file = fileName.replace('.root','.prov')
    if not os.path.isfile(prov_file):
        print(f"dumping provenance of {fileName} in {prov_file}")
        c=os.system(f"edmProvDump {fileName} > {prov_file}")
        if c!=0: return []
    #print(f"finding processes of {fileName} in {prov_file}")
    raw_proc=  os.popen(f"grep -e 'Processing History:' -A {max_proc} {prov_file} | awk '{{print $1}}'").read().split('\n')[1:]
    processes = []
    for proc_ in raw_proc:
        if '--' in proc_: break
        processes.append( proc_ )
    return processes

def last_process(fileName):
    processes_ = file_processes(fileName)
    #print(f"found processes {processes_} in {fileName}")
    if processes_: return processes_[-1]
    return None

def file_index(fileName):
    ndigits=3
    fn= fileName.replace('step','').replace('.root','')
    if '_' in fn : fn,_=fn.split('_',1)
    while ndigits:
        index = fn[-ndigits:]
        if index.isdigit():
            return int(index)
        ndigits-=1
    return None

def process_file(each_root_file):
    #print(f'processing {each_root_file} in {os.getpid()}')
    process_of_interest=['ZStoRECO','RECO','reRECO','PAT','NANO','DQM','HLT','HLT2']
    if any([pat in each_root_file for pat in ['inDQM','DQM_V']]):
        return
    processName = last_process(each_root_file)
    if not processName in process_of_interest:
        return
    #print(f"found process of interest {processName} in file {each_root_file}")
    path,fileName = each_root_file.rsplit('/',1)
    ref_path =path.replace( options.base, options.ref )
    _,fullName = path.rsplit('/',1)
    wfn,therest=fullName.split('_',1)
    wfn='wf'+wfn.replace('.','pt')
    fileindex = file_index(fileName)
    elements = therest.split('+')[:fileindex+1]
    compressedName = "".join(elements)
    #if ip !=0: compressedName += processName
    compressedName += wfn
    compressedName = compressedName.replace('.','').replace('_','')
    #print(f"compressing {path} into {compressedName}")
    output_dir = ''
    #output_dir = path+'/'
    output_dir += 'all'
    if ('inMINIAOD' in fileName):
        output_dir += '_mini'
    output_dir += '_OldVSNew'
    output_dir += '_'+compressedName
    run_comparison(fileName, path, ref_path, processName, output_dir)
    #print(f'\t{each_root_file} processed in {os.getpid()}')

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] dir1 dir2 ...")
    parser.add_option("--base", dest="base", default="base/", help="path to the file to compare with ref")
    parser.add_option("--ref", dest="ref", default="ref/", help="path to the reference files")
    parser.add_option("--procs", dest="procs", default=None, type=int, help="number of processes to run")
    (options, args) = parser.parse_args()

    if not compile_lib():sys.exit()

    all_output_root_files = glob.glob(f'{options.base}/*/step*.root')

    from multiprocessing import Pool
    print(f'{len(all_output_root_files)} files to process')
    with Pool(options.procs) as threads:
        results = [threads.apply_async(process_file, (f, )) for f in all_output_root_files]
        for r in results: r.wait()
