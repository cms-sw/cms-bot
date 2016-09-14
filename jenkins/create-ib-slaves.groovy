//script <arch> <username> <build-machine> <remote-dir>
def node_name = "ib-install-" + args[0]
def found = 0
for (s in hudson.model.Hudson.instance.slaves)
{
  if (s.name == node_name)  { println "Found Slave:" + node_name; found=1 ; break ; }
}
if (found == 0)
{ 
  remote_dir = args[3] + "/" + node_name
  workspace = remote_dir + "/jenkins-workarea"
  new_launcher = new hudson.slaves.CommandLauncher("/build/workspace/cache/cms-bot/jenkins/connectToSlaveKstart.sh "+args[1]+"@"+args[2]+" "+args[1]+" "+remote_dir)
  hudson.model.Hudson.instance.addNode(new hudson.slaves.DumbSlave(node_name, "Slave to install IBs", workspace, "1", hudson.model.Node.Mode.EXCLUSIVE , "no_label", new_launcher, new hudson.slaves.RetentionStrategy.Demand(0, 3),new LinkedList()))
  println "Created new node: "+ node_name
}
