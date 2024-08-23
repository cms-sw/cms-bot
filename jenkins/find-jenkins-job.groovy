boolean isJobMatched(params_to_match, job_parameters)
{
  def all_ok = true;
  for (p in params_to_match)
  {
    def cv="";
    try {
      cv = job_parameters[p.key];
      if ( ! (cv ==~ p.value) ){all_ok=false;}
    }
    catch ( e ) {all_ok=false;}
    if (! all_ok){break;}
  }
  return all_ok;
}

proj=args[0];
params = [:];
for (p in args[1].tokenize(";")){
  def x=p.tokenize("=");
  def v="";
  if (x[1]!=null){v=x[1];}
  params[x[0]]=v;
}
try {id2ignore=args[2].toInteger();}
catch ( e ) {id2ignore=0;}

println "Project:"+proj;
println "Params:"+params
println "Ignore Job Id:"+id2ignore

def queue = jenkins.model.Jenkins.getInstance().getQueue();
def items = queue.getItems();
println "Checking for queued jobs ..."
for (i=0;i<items.length;i++)
{
  if (items[i].task.getName()==proj)
  {
    data = [:]
    for (p in items[i].getParams().tokenize("\n")){
      def x=p.tokenize("=");
      if (! params.containsKey(x[0])){continue;}
      def v="";
      if (x[1]!=null){v=x[1];}
      data[x[0]]=v;
    }
    if (! isJobMatched(params, data)) {continue;}
    println "FOUND:queue/"+items[i].getId();
    return;
  }
}
println "No queued job matched";

println "Checking for running jobs ..."
for (it in jenkins.model.Jenkins.instance.getItem(proj).builds)
{
  if (it.isInProgress() != true){continue;}
  if (it.getNumber() == id2ignore){continue;}
  if (! isJobMatched(params, it.getBuildVariables())) {continue;}
  println "FOUND:job/"+it.getNumber();
  return;
}
println "No running job matched";
error("No project found");

