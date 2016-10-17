version = args[0];
wspace = args[1];
dryrun="true";
try{dryrun = args[2];}
catch (e) {dryrun="true";}

for (it in jenkins.model.Jenkins.instance.getItem("build-release").builds)
{
  params = it.getBuildVariables();
  if (params['CMSSW_X_Y_Z']!=version){continue;}
  arch = params['ARCHITECTURE'];
  println "#"+it.getNumber()+" "+version+"/"+arch;
  ws = it.getWorkspace();
  if (ws==null)
  {
    try{
      wsFromfile = 'grep <workspace> /var/lib/jenkins/jobs/build-release/builds/'+it.getNumber()+'/build.xml'
      ws = wsFromfile.execute().text.replaceAll(".*<workspace>","").replaceAll(" *</workspace>.*","")
    }
    catch (e) {println "Error: Unable to find workspace"; continue;}
  }
  if (dryrun == "false"){
    println "  Killing release build job #"+it.getNumber();
    try {it.doStop();}
    catch (e) {}
  }
  else{println "  DryRun: Not killing release build job #"+it.getNumber();}
  pfile = wspace+"/properties.kill-build-release-"+it.getNumber();
  println "Creating property file:"+pfile;
  def out = new File(pfile);
  out << "CMSSW_X_Y_Z="+version+"\n";
  out << "ARCHITECTURE="+arch+"\n";
  out << "BUILD_DIR="+ws+"\n";
  out << "BUILD_HOST="+it.getBuiltOn().getLauncher().getCommand().split(" ")[1]+"\n";
  out << "DRY_RUN="+dryrun+"\n";
}

