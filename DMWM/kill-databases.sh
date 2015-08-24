#! /bin/bash -e
set -x

start=`date +%s`

echo "Trying to kill earlier processes"
pkill -9 -f $PWD/deploy || true
pkill -9 -f external/mariadb || true # Kill off any other slices too
pkill -9 -f external/couchdb || true # Kill off any other slices too
pkill -9 -f external/erlang  || true # Kill off any other slices too
pkill -9 -f code/setup.py    || true # Kill off any other slices too

end=`date +%s`
runtime=$((end-start))
echo "Total time to kill databases: $runtime"







