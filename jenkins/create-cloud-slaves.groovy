for (s in hudson.model.Hudson.instance.slaves)
{
  def new_label = ""
  println "Checking "+s.name
  if (s.name =~ /^cmsbuild/)
  {
    for (l in s.labelString.split(" "))
    {
      if (l =~ /\-cloud$/)
      {
        new_label= l+"-tiny"
        println "Found label:"+l
      }
    }
  }
  if (new_label != "")
  {
     def new_name = "tiny-" + s.name
     def found=0;
     for (x in hudson.model.Hudson.instance.slaves)
     {
       if (x.name == new_name){found=1; break;}
     }
     if (found==0)
     {
      hudson.model.Hudson.instance.addNode(new hudson.slaves.DumbSlave(new_name, s.nodeDescription, s.remoteFS, "1", s.mode, new_label, s.getLauncher(), s.getRetentionStrategy(),s.getNodeProperties()))
      println "Created new node: "+ new_name
    }
  }
  else if (s.name =~ /^tiny-/)
  {
    def new_name = s.name.replaceAll(/^tiny-/,"")
    def found=0;
    print "  Looking for main node:"+new_name
    for (x in hudson.model.Hudson.instance.slaves)
    {
      if (x.name == new_name){found=1; println "  Found:"+x.name; break;}
    }
    if (found == 0)
    {
      hudson.model.Hudson.instance.removeNode(s)
      println "Remove node:"+ s.name
    }
  }
}
