#!/bin/bash -ex

JENKINS_JAR=$1
/etc/alternatives/jre_11/bin/java --add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.lang.reflect=ALL-UNNAMED -jar ${JENKINS_JAR} -jar-cache $(dirname ${JENKINS_JAR})/tmp
