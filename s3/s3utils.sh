#!/bin/sh -e
function hmac_sha1(){
  opts="sha1"
  [ $(openssl version | cut -d' ' -f2 | cut -d. -f1) -gt 1 ] && opts="dgst -sha1"
  echo -en "${1}" | openssl ${opts} -hmac "${2}" -binary | base64
}

function guess_mime() {
  m=`file -b --mime-type $1`
  if [ "$m" = "text/plain" ]; then
    case $1 in
      *.json)          m="application/json";;
      *.css)           m="text/css";;
    esac
  fi
  printf "$m"
}

function usage(){
  echo -e "$1
Usage: $0 <upload|copy|move|delete|exists|touch> [-d des-file] [-S server] [-b bucket] [-a acl] [-m mime-type] [-D] [-h] <-s file-name | file-name>
  -s src-file Source/local file
  -d des-obj  Destination file/Object name, default is <src-file>
  -S server   AWS host/server, default: s3.cern.ch
  -b bucket   S3 bucket name, default: cmsrep
  -a acl      ACL, default: public-read
  -m mime     Mime-type, default: guess from the source file extension.
  -c credentials File with aws_secret_access_key and aws_access_key_id, default is ~/.aws/credentials
  -D          Enable debug output.
  -h          Print this help message."
  exit $2
}

function move_file(){
  copy_file $1 $2
  delete_file $1
}

function touch_file(){
  xdate=$(date +%s)
  copy_file $1 ${1}-${xdate}
  move_file ${1}-${xdate} $1
}

function copy_file(){
  date=$(date +"%a, %d %b %Y %T %z")
  str="PUT\n\n\n${date}\nx-amz-acl:${ACL}\nx-amz-copy-source:/${BUCKET}/${1}\n/${BUCKET}/${2}"
  sign=$(hmac_sha1 "${str}"  "${aws_secret_access_key}")
  curl -s -X PUT \
    -H "Host: ${BUCKET}.${SERVER}" \
    -H "Date: $date" \
    -H "X-Amz-Acl: ${ACL}" \
    -H "X-Amz-Copy-Source: /${BUCKET}/${1}" \
    -H "Authorization: AWS ${aws_access_key_id}:${sign}" \
    "https://${BUCKET}.${SERVER}/${2}"
  has_file ${2}
}

function upload_file(){
  sha256=$(sha256sum ${1} | cut -d' ' -f1)
  date=$(date +"%a, %d %b %Y %T %z")
  xdate=$(date +%s)
  str="PUT\n\n${MIME}\n${date}\nx-amz-acl:${ACL}\nx-amz-meta-sha256:${sha256}\nx-amz-meta-xdate:${xdate}\n/${BUCKET}/${2}"
  sign=$(hmac_sha1 "${str}"  "${aws_secret_access_key}")
  curl -s -X PUT -T "${1}" \
    -H "Host: ${BUCKET}.${SERVER}" \
    -H "Date: $date" \
    -H "Content-Type: ${MIME}" \
    -H "X-Amz-Acl: ${ACL}" \
    -H "X-Amz-Meta-Sha256: ${sha256}" \
    -H "X-Amz-Meta-Xdate: ${xdate}" \
    -H "Authorization: AWS ${aws_access_key_id}:${sign}" \
    "https://${BUCKET}.${SERVER}/${2}"
  has_file ${2}
}

function delete_file(){
  date=$(date +"%a, %d %b %Y %T %z")
  str="DELETE\n\n\n${date}\n/${BUCKET}/${1}"
  sign=$(hmac_sha1 "${str}"  "${aws_secret_access_key}")
  curl -s -X DELETE \
    -H "Host: ${BUCKET}.${SERVER}" \
    -H "Date: $date" \
    -H "Authorization: AWS ${aws_access_key_id}:${sign}" \
    "https://${BUCKET}.${SERVER}/${1}"
}

function has_file(){
  RES_TXT=$(curl -s --head https://${BUCKET}.${SERVER}/${1} 2>&1)
  RES=$(echo "${RES_TXT}" | grep '^HTTP' | head -1 | cut -d' ' -f2)
  if [ "${RES}" != "200" ] ; then
    echo "${RES_TXT}"
    echo "Error: https://${BUCKET}.${SERVER}/${1} file does not exist."
    exit 1
  fi
}

function ask_permissions(){
  if ! $FORCE ; then
    read -p "Do you really want to $1:(yY/nN): " RES
    case "$RES" in
      y|Y) ;;
      n|N) echo "Nothing done" ; exit 0;;
      * ) echo "Invalid response: $RES"; exit 1;;
    esac
  fi
}

CREDENTIALS="${HOME}/.aws/credentials"
BUCKET="cmsrep"
SRC_FILE=""
DES_FILE=""
ACL="public-read"
MIME=""
SERVER="s3.cern.ch"
XFILE=""
CMD="upload"
FORCE=false
case "$1" in
  u|up|upload)  CMD="upload" ; shift ;;
  c|cp|copy)    CMD="copy"   ;;
  e|exists)     CMD="exists" ;;
  m|mv|move)    CMD="move"   ;;
  d|del|delete) CMD="delete" ;;
  r|rm|remove)  CMD="delete" ;;
  t|touch)      CMD="touch"  ;;
  -*)                        ;;
  *) [ ! -f "$1" ]  && usage "Invalid command: $1" 1;;
esac
[ "$CMD" = "upload" ] || shift
while [[ $# -gt 0 ]] ; do
  opt=$1; shift
  case $opt in
    -s) SRC_FILE="$1"; shift ;;
    -d) DES_FILE="$1"; shift ;;
    -a) ACL="$1";      shift ;;
    -m) MIME="$1";     shift ;;
    -b) BUCKET="$1";   shift ;;
    -S) SERVER="$1";   shift ;;
    -c) CREDENTIALS="$1"; shift ;;
    -f) FORCE=true;;
    -D) set -x;;
    -h) usage "" 0;;
    *) XFILE=$opt ;;
  esac
done

if [ "$CMD" = "exists" ] ; then
  [ "${SRC_FILE}" = "" ] && SRC_FILE=${XFILE}
  [ "$SRC_FILE" = "" ]   && usage "Error: Missing file name/path. Use '$0 exists file-path-under-backet'" 1
  has_file $SRC_FILE
else
  [ -f "${CREDENTIALS}" ] && eval $(grep '^[a-z]' ${CREDENTIALS} | grep '=' | sed 's| ||g')
  [ "${aws_secret_access_key}" = "" ] && echo "Error: aws_secret_access_key not set in ${CREDENTIALS} file" && exit 1
  [ "${aws_access_key_id}" = ""     ] && echo "Error: aws_access_key_id not set in ${CREDENTIALS} file" && exit 1
  [ "$SRC_FILE" = "" ]   && SRC_FILE=${XFILE}
  [ "$SRC_FILE" = "" ]   && usage "Error: Missing source file name/path. Use -s file-path-under-backet" 1
  if [ "$CMD" = "delete" ] ; then
    ask_permissions "delete S3:${BUCKET}/${SRC_FILE}"
    delete_file ${SRC_FILE}
  elif [ "$CMD" = "touch" ] ; then
    ask_permissions "update timestamp of S3:${BUCKET}/${SRC_FILE}"
    touch_file ${SRC_FILE}
  elif [ "$CMD" = "copy" -o "$CMD" = "move" ] ; then
    if [ "${DES_FILE}" = "" -o "${DES_FILE}" = "${SRC_FILE}" ] ; then
      echo "Error: Invalid destination file '${DES_FILE}'"
      exit 1
    fi
    ask_permissions "$CMD S3:${BUCKET}/${SRC_FILE} to S3:${BUCKET}/${DES_FILE}"
    if [ $CMD = "copy" ] ; then
      copy_file ${SRC_FILE} ${DES_FILE}
    elif [ $CMD = "move" ] ; then
      move_file ${SRC_FILE} ${DES_FILE}
    fi
  else
    [ "${DES_FILE}" = "" ] && DES_FILE="${SRC_FILE}"
    DES_FILE=$(echo -n "$DES_FILE" | sed "s|^/*||;s|\/$|\/$(basename $SRC_FILE)|")
    [ "$MIME" = "" ] && MIME=$(guess_mime $SRC_FILE)
    [ ! -e "$SRC_FILE" ] && usage "Error: No such file: $SRC_FILE" 1
    ask_permissions "upload local file ${SRC_FILE} to S3:${BUCKET}/${DES_FILE}"
    echo "Uploading: $SRC_FILE ($MIME) to $BUCKET:$DES_FILE"
    upload_file ${SRC_FILE} ${DES_FILE}
    echo "$SRC_FILE successfully uploaded to backet $BUCKET as $DES_FILE."
  fi
fi
