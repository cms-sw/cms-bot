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
Usage: $0 -s src-file [-e] [-d des-file] [-S server] [-b bucket] [-a acl] [-m mime-type] [-D] [-h]
  -s src-file Source/local file
  -e          Check if src-file exists in S3, default is upload src to des
  -d des-obj  Destination file/Object name, default is <src-file>
  -S server   AWS host/server, default: s3.cern.ch
  -b bucket   S3 bucke name, default: cmsrep
  -a acl      ACL, default: public-read
  -m mime     Mime-type, default: guess from the source file extension.
  -c credentials File with aws_secret_access_key and aws_access_key_id, default is ~/.aws/credentials
  -D          Enable debug output.
  -h          Print this help message."
  exit $2
}

function upload_file(){
  sha256=$(sha256sum ${SRC_FILE} | cut -d' ' -f1)
  date=$(date +"%a, %d %b %Y %T %z")
  xdate=$(date +%s)
  str="PUT\n\n${MIME}\n${date}\nx-amz-acl:${ACL}\nx-amz-meta-sha256:${sha256}\nx-amz-meta-xdate:${xdate}\n/${BUCKET}/${DES_FILE}"
  sign=$(hmac_sha1 "${str}"  "${aws_secret_access_key}")
  curl -X PUT -T "${SRC_FILE}" \
    -H "Host: ${BUCKET}.${SERVER}" \
    -H "Date: $date" \
    -H "Content-Type: ${MIME}" \
    -H "X-Amz-Acl:${ACL}" \
    -H "X-Amz-Meta-Sha256: ${sha256}" \
    -H "X-Amz-Meta-Xdate: ${xdate}" \
    -H "Authorization: AWS ${aws_access_key_id}:${sign}" \
    "https://${BUCKET}.${SERVER}/${DES_FILE}"
}

function has_file(){
  RES_TXT=$(curl -s --head https://${BUCKET}.${SERVER}/${DES_FILE} 2>&1)
  RES=$(echo "${RES_TXT}" | grep '^HTTP' | head -1 | cut -d' ' -f2)
  if [ "${RES}" != "200" ] ; then
    echo "${RES_TXT}"
    echo "Error: https://${BUCKET}.${SERVER}/${DES_FILE} file does not exist."
    exit 1
  fi
}

CREDENTIALS="${HOME}/.aws/credentials"
BUCKET="cmsrep"
SRC_FILE=""
DES_FILE=""
ACL="public-read"
MIME=""
SERVER="s3.cern.ch"
CHK_EXISTS=false
XFILE=""
while [[ $# -gt 0 ]] ; do
  opt=$1; shift
  case $opt in
    -s) SRC_FILE="$1"; shift ;;
    -d) DES_FILE="$1"; shift ;;
    -a) ACL="$1";      shift ;;
    -m) MIME="$1";     shift ;;
    -b) BUCKET="$1";   shift ;;
    -S) SERVER="$1";   shift ;;
    -e) CHK_EXISTS=true;;
    -c) CREDENTIALS="$1"; shift ;;
    -D) set -x;;
    -h) usage "" 0;;
    *) XFILE=$opt ;;
  esac
done

if $CHK_EXISTS ; then
  [ "${DES_FILE}" = "" ] && DES_FILE=${XFILE}
else
  [ "$SRC_FILE" = "" ]   && SRC_FILE=${XFILE}
  [ "$SRC_FILE" = "" ]   && usage "Error: Missing source file name/path." 1
  [ "${DES_FILE}" = "" ] && DES_FILE="${SRC_FILE}"
  DES_FILE=$(echo -n "$DES_FILE" | sed "s|^/*||;s|\/$|\/$(basename $SRC_FILE)|")
fi

#Checking for file in S3
$CHK_EXISTS && has_file && exit 0

#Upload local file to S3
[ "$MIME" = "" ] && MIME=$(guess_mime $SRC_FILE)
[ ! -e "$SRC_FILE" ] && usage "Error: No such file: $SRC_FILE" 1

[ -f "${CREDENTIALS}" ] && eval $(grep '^[a-z]' ${CREDENTIALS} | grep '=' | sed 's| ||g')
[ "${aws_secret_access_key}" = "" ] && echo "Error: aws_secret_access_key not set in ${CREDENTIALS} file" && exit 1
[ "${aws_access_key_id}" = ""     ] && echo "Error: aws_access_key_id not set in ${CREDENTIALS} file" && exit 1

echo "Uploading: $SRC_FILE ($MIME) to $BUCKET:$DES_FILE"
upload_file
has_file
echo "$SRC_FILE successfully uploaded to backet $BUCKET as $DES_FILE."
