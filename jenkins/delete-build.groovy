import jenkins.model.Jenkins

projName=args[0];
buildId=arg[1].toInteger();

println "Removing build number "+buildId+" for "+projName;
Jenkins.instance.getItemByFullName(projName).builds.findAll
{ 
  it.number == buildId 
}.each
{ 
  it.delete() 
};
