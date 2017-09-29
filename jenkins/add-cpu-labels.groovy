slave = hudson.model.Hudson.instance.slaves.find { slave -> slave.nodeName.equals(args[0]) }
def cur_lab = slave.labelString.replaceAll(/  +/,' ').trim()
def release_build=cur_lab.contains("release-build");
if (!(cur_lab =~ /\s*no_label\s*/))
{
  def xlabs=[args[1], args[2], "auto-label"];
  def items = args[2].split("_");
  for (String y : items){xlabs.push(y);}
  if (args[2]!="")
  {
    if (slave.name =~ /^cmsbuild\d+$/)
    {
      xlabs.push(args[2]+"-cloud");
      xlabs.push("cloud");
      release_build=true;
    }
    if (args[1]!=""){xlabs.push(args[2]+"-"+args[1]);}
    if (release_build){xlabs.push(args[2]+"-release-build");}
  }
  if (release_build){xlabs.push("release-build");}
  if (args[3]=="docker")
  {
    xlabs.push("docker");
    if (items.length==2)
    {
      xlabs.push("docker-"+items[1]);
      if (args[1]!=""){xlabs.push("docker-"+items[1]+"-"+args[1]);}
    }
    if (args[1]!=""){xlabs.push("docker-"+args[1]);}
  }
  new_lab =  xlabs.join(" ").replaceAll(/\s\s+/,' ').trim();
  println "New Labels:"+new_lab
  println "Cur Labels:"+cur_lab
  if (new_lab != cur_lab)
  {
    slave.setLabelString(new_lab)
    println "Changing labels: "+cur_lab+"->"+new_lab 
  }
}
else
{
  println "Not changing labels due to explicit 'no_label'"
}
