import jenkins.model.*
import java.util.logging.Logger

Jenkins.instance.pluginManager.plugins.each{
  plugin -> 
    println ("${plugin.getShortName()}:${plugin.getVersion()}")
}

