#!/bin//bash -ex
BASE=$1
REL=$2

for d in `find $BASE -maxdepth 3 -mindepth 3 -name $REL -type d` ; do
  [ -d $d/external ] || continue
  pushd $d
    for L in `find external -path '*/data/*' -type l`; do
      lnk=`readlink -n $L 2>&1`
      case $lnk in
        */build-any-ib/w/share/* )
          rl=`echo $L | sed -e 's|[^/]*/|../|g;' | xargs dirname`
          al=`echo $lnk | sed -e "s|^.*/build-any-ib/w/|../../../../$rl/|"`
          echo $d/$L $al
          rm -f $L
          ln -sf $al $L
          ;;
      esac
    done
  popd
done

