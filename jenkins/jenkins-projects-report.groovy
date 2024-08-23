/**
 * extracts metadata about jenkins jobs from jenkins and  dumps in json format
 */

import jenkins.*
import jenkins.model.*
import hudson.*
import hudson.model.*
import groovy.json.*

def info = [:]
for (p in Jenkins.instance.projects) {
    def new_map = [:]
    new_map['job_name'] = p.name
    new_map['job_desc'] = p.description
    new_map['upstream'] = []
    new_map['downstream'] = []
    new_map['triggers_from'] = []
    new_map['subprojects'] = []

    p.getUpstreamProjects().each { project -> new_map['upstream'] << project.getDisplayName() }
    p.getDownstreamProjects().each { project -> new_map['downstream'] << project.getDisplayName() }
    p.getBuildTriggerUpstreamProjects().each { project -> new_map['triggers_from'] << project.getDisplayName() }

    for (b in p.builders) {
        if (b in hudson.plugins.parameterizedtrigger.TriggerBuilder) {
            b.configs.projects.each { project -> new_map['subprojects'] << project }
        }
    }
    info[p.name] = new_map
}
def json = JsonOutput.toJson(info)
def file1 = new File('/tmp/report_gen.txt')
file1.write json
