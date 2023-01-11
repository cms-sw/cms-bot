import glob, os, sys

def makedirs(dir):
    try:
        os.makedirs(dir, exist_ok=True)
    except:
        if not os.path.exists(dir):
            os.makedirs(dir)

## commented lines are mostly python3 fstring syntax that we cannot use until we totally loose python2 support in the PR validation

def autoLoadEnabler():
    if os.path.isfile( os.path.join(os.environ['CMSSW_RELEASE_BASE'],'src/FWCore/FWLite/interface/FWLiteEnabler.h')):
        return 'FWLiteEnabler::enable();'
    else:
        return 'AutoLibraryLoader::enable();'

def compile_lib():
    lib_dir = 'validate_lib'
    #if not os.path.isfile(f'{lib_dir}/validate_C.so'):
    if not os.path.isfile('%s/validate_C.so'%(lib_dir,)):
        makedirs(lib_dir)
        if not 'VALIDATE_C_SCRIPT' in os.environ or not os.environ['VALIDATE_C_SCRIPT']:
            os.environ['VALIDATE_C_SCRIPT'] = os.path.join(os.environ['HOME'],'tools','validate.C')
        if os.path.isfile(os.environ['VALIDATE_C_SCRIPT']):
            #os.system(f"cp $VALIDATE_C_SCRIPT {lib_dir}/validate.C")
            os.system("cp $VALIDATE_C_SCRIPT %s/validate.C"%(lib_dir,))
        #command = f'cd {lib_dir};'+'echo -e "gSystem->Load(\\"libFWCoreFWLite.so\\");{autoLoadEnabler()}\n .L validate.C+ \n .qqqqqq\" | root -l -b'
        command = 'cd %s;'%(lib_dir,)+'echo -e "gSystem->Load(\\"libFWCoreFWLite.so\\");%s\n .L validate.C+ \n .qqqqqq\" | root -l -b'%(autoLoadEnabler(),)
        #print(f"compiling library with {command}")
        print("compiling library with %s"%(command,))
        os.system( command )
    os.environ['LD_LIBRARY_PATH'] = ':'.join([os.path.join(os.getcwd(),'validate_lib'),os.environ['LD_LIBRARY_PATH']])
    #return os.path.isfile(f'{lib_dir}/validate_C.so')
    return os.path.isfile('%s/validate_C.so'%(lib_dir,))

def run_comparison(fileName, base_dir, ref_dir, processName, spec, output_dir):
    base_file=os.path.join(base_dir,fileName)
    ref_file=os.path.join(ref_dir,fileName)
    if not os.path.isfile(base_file) or not os.path.isfile(ref_file):
        return False
    logFile=fileName.replace('.root','.log')
    makedirs(output_dir)
    #command = f'cd {output_dir}; echo -e "gSystem->Load(\\"libFWCoreFWLite.so\\");{autoLoadEnabler()}gSystem->Load(\\"validate_C.so\\");validate(\\"{spec}\\",\\"{base_file}\\",\\"{ref_file}\\",\\"{processName}\\");\n.qqqqqq" | root -l -b >& {logFile}'
    command = 'cd %s;'%output_dir + 'echo -e "gSystem->Load(\\"libFWCoreFWLite.so\\");%sgSystem->Load(\\"validate_C.so\\");validate(\\"%s\\",\\"%s\\",\\"%s\\",\\"%s\\");\n.qqqqqq" | root -l -b >& %s'%(autoLoadEnabler(), spec, base_file, ref_file, processName, logFile)
    #print(f"running comparison with {command}")
    #print(f"log of comparing {fileName} process {processName} from {base_dir} and {ref_dir} into {output_dir} with spec {spec} shown in {logFile}")
    print("log of comparing %s process %s from %s and %s into %s with spec %s shown in %s"%(fileName, processName, base_dir, ref_dir, output_dir, spec, logFile ))
    c=os.system( command )
    return True

def file_processes(fileName):
    max_proc=20
    prov_file = fileName+'.edmProvDump'
    if not os.path.isfile(prov_file):
        #print(f"dumping provenance of {fileName} in {prov_file}")
        print("dumping provenance of %s in %s"%(fileName, prov_file))
        #c=os.system("edmProvDump {fileName} > {prov_file}")
        c=os.system("edmProvDump %s > %s"%(fileName, prov_file))
        if c!=0: return []
    #print(f"finding processes of {fileName} in {prov_file}")
    #raw_proc=  os.popen(f"grep -e 'Processing History:' -A {max_proc} {prov_file} | awk '{{print $1}}'").read().split('\n')[1:]
    raw_proc=  os.popen("grep -e 'Processing History:' -A %s %s | awk '{print $1}'"%(max_proc, prov_file)).read().split('\n')[1:]
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
    ref_path,fileName = each_root_file.rsplit('/',1)
    path = ref_path.replace( options.ref, options.base )
    _,fullName = path.rsplit('/',1)
    wfn,therest=fullName.split('_',1)
    wfn='wf'+wfn.replace('.','p')
    # specify what are the specific branches to look at
    spec = 'all'
    if ('inMINIAOD' in fileName): spec += '_mini'

    # the compressed name should uniquely identify the workflow and the output file
    compressedName = therest.replace('+','').replace('.','').replace('_','')
    compressedName += fileName.replace('.root','')
    compressedName += wfn
    #print(f"compressing {path} into {compressedName}")
    output_dir = os.path.join(#'OldVSNew',
                              fullName,
                              #'_'.join([spec,processName,fileName.replace('.root','').split('_')[-1] if '_' in fileName else '']),
                              '_'.join([spec,processName,fileName.replace('.root','')])
                          )


    run_comparison(fileName, path, ref_path, processName, spec, output_dir)
    #print(f'\t{each_root_file} processed in {os.getpid()}')

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser(usage="%prog [options]")
    parser.add_option("--base", dest="base", default="base/", help="path to the file to compare with ref")
    parser.add_option("--ref", dest="ref", default="ref/", help="path to the reference files")
    parser.add_option("--wf", dest="workflow", default="*", help="pattern for listing the workflows to run the comparison for {base}/{wf}_*/...")
    parser.add_option("--procs", dest="procs", default=None, type=int, help="number of processes to run")
    (options, args) = parser.parse_args()

    if not compile_lib():sys.exit()

    #all_output_root_files = glob.glob(f'{options.base}/{options.workflow}_*/step*.root')
    all_output_root_files = glob.glob('%s/%s_*/step*.root'%(options.ref,options.workflow))

    #print(f'{len(all_output_root_files)} files to process')
    print('%d files to process'%(len(all_output_root_files)))

    if options.procs==0:
        for afile in all_output_root_files:
            process_file(afile)
    else:
        from multiprocessing import Pool
        #with Pool(options.procs) as threads: #only python3
        #    results = [threads.apply_async(process_file, (f, )) for f in all_output_root_files]
        #    for r in results: r.wait()
        threads = Pool(options.procs)
        results = [threads.apply_async(process_file, (f, )) for f in all_output_root_files]
        for r in results:
            r.wait()
