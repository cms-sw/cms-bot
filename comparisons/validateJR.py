#!/usr/bin/env python3
import glob, os, sys


def compile_lib():
    if not os.path.isfile('validate_C.so'):
        command = 'echo -e \"gSystem->Load(\"libFWCoreFWLite.so\");AutoLibraryLoader::enable();FWLiteEnabler::enable();.L validate.C+ .qqqqqq\" | root -l -b'
        print(f"compiling library with {command}")
        os.system( command )
        return True
    return os.path.isfile('validate_C.so')

def run_comparison(fileName, base_dir, ref_dir, processName, output_dir):
    base_file=base_dir+"/"+fileName
    ref_file=ref_dir+"/"+fileName
    logFile=output_dir+"/"+fileName+".log"
    os.makedirs(output_dir ,exist_ok=True)
    what_is_called_step_in_the_script = output_dir
    command = f'echo -e "gSystem->Load(\\"libFWCoreFWLite.so\\");AutoLibraryLoader::enable();FWLiteEnabler::enable();gSystem->Load(\\"validate_C.so\\");validate(\\"{what_is_called_step_in_the_script}\\",\\"{base_file}\\",\\"{ref_file}\\",\\"{processName}\\");\n.qqqqqq" | root -l -b >& {logFile}'
    #print(f"running comparison with {command}")
    print(f"comparing {fileName} from {base_dir} and {ref_dir} into {output_dir}")
    c=os.system( command )
    #print(f"comparison exit signal is {c}")
    #if c!=0: return False
    return True

def file_processes(fileName):
    if any([pat in fileName for pat in ['inDQM','DQM_V']]):
        return []
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

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options] dir1 dir2 ...")
    parser.add_option("--base", dest="base", default="base/", help="path to the file to compare with ref")
    parser.add_option("--ref", dest="ref", default="ref/", help="path to the reference files")
    (options, args) = parser.parse_args()

    if not compile_lib():
        sys.exit()
    process_of_interest=['RECO','reRECO','PAT','NANO','DQM','HLT','HLT2']

    all_output_root_files = glob.glob(f'{options.base}/*/*.root')
    for each_root_file in all_output_root_files:
        processName = last_process(each_root_file)
        if processName in process_of_interest:
            print(f"found process of interest {processName} in file {each_root_file}")
            path,fileName = each_root_file.rsplit('/',1)
            ref_path =path.replace( options.base, options.ref )
            _,compressedName = path.rsplit('/',1)
            wfn,therest=compressedName.split('_',1)
            wfn='wf'+wfn.replace('.','pt')
            fileindex = file_index(fileName)
            elements = therest.split('+')[:fileindex+1]
            compressedName = "".join(elements) + wfn
            compressedName = compressedName.replace('.','').replace('_','')
            print(f"compressing {path} into {compressedName}")
            output_dir = ''
            #output_dir = path+'/'
            output_dir += 'all'
            if ('inMINIAOD' in fileName):
                output_dir += '_mini'
            output_dir += '_OldVSNew'
            output_dir += '_'+compressedName
            run_comparison(fileName, path, ref_path, processName, output_dir)
            break



