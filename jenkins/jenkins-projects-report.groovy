import jenkins.*
import jenkins.model.*
import hudson.*
import hudson.model.* 
import groovy.json.*
def info = [:]
for (p in Jenkins.instance.projects)
{
  def new_map = [:]
  def list1 = []
  def list2 = []
  def list3 = []
  def list4 = []
  new_map['job_name'] = p.name  
  new_map['job_desc'] = p.description   
  p.getUpstreamProjects().each { project ->  list1 << project.getDisplayName() }
  new_map['upstream']=list1
  p.getDownstreamProjects().each { project ->  list2 << project.getDisplayName() }
  new_map['downstream'] = list2
  p.getBuildTriggerUpstreamProjects().each { project ->  list3 << project.getDisplayName() }
  new_map['triggers_from'] = list3 
  for (b in p.builders)
    {
      if (b in hudson.plugins.parameterizedtrigger.TriggerBuilder)
         {
            b.configs.projects.each {project -> list4 << project }
         }
    }
   new_map['subprojects'] = list4
   info[p.name] = new_map
}
def json = JsonOutput.toJson(info)
def file1 = new File('/tmp/report_gen.txt')
file1.write json
