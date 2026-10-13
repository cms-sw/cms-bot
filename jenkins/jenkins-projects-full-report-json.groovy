/**
 * Extracts metadata about Jenkins jobs and dumps it in JSON format.
 */

import jenkins.*
import jenkins.model.*
import hudson.*
import hudson.model.*
import groovy.json.*

def projectMap = [:]
def viewMap = [:]
def mainMap = [:]

mainMap['projects'] = projectMap
mainMap['views'] = viewMap

Hudson.instance.getViews().each { vIt ->
    def viewDescription = [:]
    viewDescription['name'] = vIt.getDisplayName()
    viewDescription['view_type'] = vIt.getDescriptor().getDisplayName()
    viewDescription['description'] = vIt.getDescription()
    viewDescription['project_names'] = []

    vIt.items.each { pIt ->
        viewDescription['project_names'] << pIt.getDisplayName()
    }

    viewMap[vIt.getDisplayName()] = viewDescription
}

for (p in Jenkins.instance.getAllItems(Job.class)) {
    def projectDescription = [:]

    projectDescription['project_name'] = p.getDisplayName()
    projectDescription['project_desc'] = p.getDescription()
    projectDescription['upstream'] = []
    projectDescription['downstream'] = []
    projectDescription['triggers_from'] = []
    projectDescription['subprojects'] = []
    projectDescription['build_parameters'] = []
    projectDescription['scheduled_triggers'] = []
    projectDescription['is_disabled'] = p.isDisabled()

    // These methods and builders are specific to AbstractProject
    // and are not available on Pipeline WorkflowJob instances.
    if (p instanceof AbstractProject) {
        p.getUpstreamProjects().each { project ->
            projectDescription['upstream'] << project.getDisplayName()
        }

        p.getDownstreamProjects().each { project ->
            projectDescription['downstream'] << project.getDisplayName()
        }

        p.getBuildTriggerUpstreamProjects().each { project ->
            projectDescription['triggers_from'] << project.getDisplayName()
        }

        for (b in p.builders) {
            if (b instanceof hudson.plugins.parameterizedtrigger.TriggerBuilder) {
                b.configs.projects.each { project ->
                    projectDescription['subprojects'] << project
                }
            }
        }
    }

    p.getProperties().each { k, v ->
        if (v instanceof ParametersDefinitionProperty) {
            v.getParameterDefinitions().each { d ->
                def defaultParameter = d.getDefaultParameterValue()

                def buildParametersMap = [
                    name         : d.getName(),
                    desciption   : d.getDescription(),
                    type         : d.getType(),
                    default_value : defaultParameter?.getValue()
                ]

                projectDescription['build_parameters'] << buildParametersMap
            }
        }
    }

    p.getTriggers().each { k, v ->
        projectDescription['scheduled_triggers'] <<
            [k.getDisplayName(), v.getSpec()]
    }

    projectMap[p.getDisplayName()] = projectDescription
}

def json = JsonOutput.toJson(mainMap)
def file1 = new File(args[0])
file1.write(json, 'UTF-8')
