#!/bin/bash -ex

JAVA_CMD=$1

/etc/alternatives/jre_11/bin/java -version # java > 11 needed for Jenkins connection
/etc/alternatives/jre_11/bin/java --add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.lang.reflect=ALL-UNNAMED -jar $JAVA_CMD -jar-cache $(dirname $JAVA_CMD)/tmp
