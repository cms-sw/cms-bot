slave = hudson.model.Hudson.instance.slaves.find { slave -> slave.nodeName.equals(args[0]) }
def cur_lab = slave.labelString.replaceAll(/  +/,' ').trim()
if (!(cur_lab =~ /\s*no_label\s*/))
{
  def new_lab = cur_lab.replaceAll(/\s*[^\s]+-cores(\d+)\s*/,' ').replaceAll(/\s*docker\s*/,' ')
  if ((args[1]!="") && (args[2]!=""))
  {
    new_lab = new_lab.replaceAll(/\s*[^\s]+-(GenuineIntel|AuthenticAMD)\s*/,' ').replaceAll(/\s*([^\s]*-|)/+args[2]+/(-[^\s]+|)\s*/,' ')
    new_lab = new_lab + args[2] + " " + args[2]+"-"+args[1]
    if (slave.name =~ /^cmsbuild\d+$/) {new_lab = new_lab + " docker " + args[2]+"-cloud"}
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
