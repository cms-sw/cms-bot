for (slave in hudson.model.Hudson.instance.slaves)
{
  comp = slave.getComputer();
  if (comp.isOffline())
  {
    offCause = comp.getOfflineCause();
    if (offCause == null){continue;}
    println slave.name+":"+offCause;
    if (offCause)
    {
      if (offCause.getClass() == org.jenkinsci.plugins.detection.unreliable.slave.BuildStatisticListener$1) 
      {
        println "Trying to reconnect:"+slave.name;
        println comp.cliOnline();
      }
    }
  }
}
