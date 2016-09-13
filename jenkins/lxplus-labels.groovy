slave = hudson.model.Hudson.instance.slaves.find { slave -> slave.nodeName.equals(args[0]) }
def cur_lab = slave.labelString.replaceAll(/  +/,' ').trim()
def new_lab = cur_lab.replaceAll(/\s*[^- ]+?-lxplus-(AuthenticAMD|GenuineIntel)/,'').replaceAll(/\.cern\.ch/,'').replaceAll(/\s*lxplus[0-9][0-9]+/,'')+" "+args[3]
if (args[2] == "yes")
{
  new_lab = new_lab.replaceAll(/  +/,' ').trim() + " " + args[4]+'-lxplus-'+args[1]
}
if (new_lab != cur_lab)
{
  slave.setLabelString(new_lab)
  println "Changing labels: "+cur_lab+"->"+new_lab 
}
