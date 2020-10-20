slave = hudson.model.Hudson.instance.slaves.find { slave -> slave.nodeName.equals(args[0]) }
def cur_lab = slave.labelString.replaceAll(/  +/,' ').trim()
def new_lab=""
for(int i = 1;i<args.length;i++) {new_lab+=args[i]+" "}
new_lab=new_lab.trim()
if (!(cur_lab =~ /\s*no_label\s*/))
{
  if (new_lab != cur_lab)
  {
    slave.setLabelString(new_lab)
    println "Changing labels: "+cur_lab+"->"+new_lab
  }
}
