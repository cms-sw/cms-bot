import jenkins.model.*
import hudson.model.*

projName=args[0];
buildId=args[1].toInteger();

println "Retrying build number "+buildId+" for "+projName;
def job = Jenkins.instance.getItemByFullName(projName)
def my_job = job.getBuildByNumber(buildId)

def actions = my_job.getActions(ParametersAction)
println actions
job.scheduleBuild2(0, actions.toArray(new ParametersAction[actions.size()]))
