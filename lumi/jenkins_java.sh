#!/bin/bash -ex

JENKINS_JAR=$1
JAVA_CMD="/etc/alternatives/jre_17/bin/java"
[ -e /etc/alternatives/jre_21/bin/java ] && JAVA_CMD="/etc/alternatives/jre_21/bin/java"
$JAVA_CMD --add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.lang.reflect=ALL-UNNAMED -jar ${JENKINS_JAR} -jar-cache $(dirname ${JENKINS_JAR})/tmp
