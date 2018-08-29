proj=args[0];
build_number=args[1].toInteger();
println "Checking running jobs for "+proj;
for (it in jenkins.model.Jenkins.instance.getItem(proj).builds)
{
  if (it.getNumber() != build_number){continue;}
  println "Found build with progress "+it.isInProgress()
  if (it.isInProgress() == true)
  {
    it.doStop();
    println "  Stopped Job";
  }
  break;
}

