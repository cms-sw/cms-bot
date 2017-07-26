slave = hudson.model.Hudson.instance.slaves.find { slave -> slave.nodeName.equals(args[0]) }
def cur_lab = slave.labelString.replaceAll(/  +/,' ').trim()
if (!(cur_lab =~ /\s*no_label\s*/))
{
  def xlabs=[args[1], args[2]];
  def items = args[2].split("_");
  for (String y : items){xlabs.push(y);}
  if (args[2]!="")
  {
    if (slave.name =~ /^cmsbuild\d+$/){xlabs.push(args[2]+"-cloud"); xlabs.push("cloud");}
    if (args[1]!=""){xlabs.push(args[2]+"-"+args[1]);}
  }
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
  println xlabs.join(" ").replaceAll(/\s\s+/,' ').trim();

  def new_lab = cur_lab.replaceAll(/\s*docker\s*/,' ')
  if ((args[1]!="") && (args[2]!=""))
  {
    new_labs1="";
    for (String y : new_lab.split(" "))
    {
      skip=false;
      for (String x : items){if (y.contains(x)){skip=true;}}
      if (skip){continue;}
      new_labs1=new_labs1+" "+y;
    }
    new_lab = new_labs1 + " " + args[2] + " " + args[2]+"-"+args[1];
    if (slave.name =~ /^cmsbuild\d+$/) {new_lab = new_lab + " " + args[2] + "-cloud"}
    if (args[3]=="docker")
    {
      if (items.length==2){new_lab = new_lab + " docker docker-" + items[1]}
    }
  }
  new_lab = new_lab.replaceAll(/\s\s+/,' ').trim()
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
