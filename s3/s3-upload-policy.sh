#!/bin/sh -e

function hmac_sha256 {
  echo -n "$2" | openssl dgst -sha256 -mac HMAC -macopt "$1" | sed 's|^.* ||'
}

function guess_mime()
{
  m=`file -b --mime-type $1`
  if [ "$m" = "text/plain" ]; then
    case $1 in
      *.txt)           m="text/plain";;
      *.json)          m="application/json";;
      *.css)           m="text/css";;
      *rss*.xml|*.rss) m="application/rss+xml";;
    esac
  fi
  printf "$m"
}

function usage()
{
  echo "Usage: $0 "
  echo "  -s|--src <src-file> : Source/local file"
  echo "  [-e|--exists] : cehck if src-file exists in S3, default is upload src to des"
  echo "  [-d|--des <des>] #Default=<src-file>"
  echo "  [-s|--servcie <service>] #Default: s3"
  echo "  [-D|--domain <domain>]   #Default: cern.ch"
  echo "  [-b|--bucket <bucket>]   #Default: cmsrep"
  echo "  [-r|--region <region>]   #Default: us"
  echo "  [-a|--acl <acl>]         #Default: public-read"
  echo "  [-m|--mime <mime-type>]  #Default: guess from the file extension"
  echo "  [--debug]"
  exit $1
}

function get_signature_string()
{
  cat <<POLICY | openssl base64
  { "expiration": "${EXP_DATE}T12:00:00.000Z",
  "conditions": [
      {"acl": "$ACL" },
      {"bucket": "$BUCKET" },
      ["starts-with", "\$key", ""],
      ["starts-with", "\$content-type", ""],
      ["content-length-range", 1, `ls -l -H "$SRC_FILE" | awk '{print $5}' | head -1`],
      {"content-md5": "$SRC_MD5" },
      {"x-amz-date": "$CDATE" },
      {"x-amz-credential": "${aws_access_key_id}/${EXP_DATE_STR}/${REGION}/${SERVICE}/aws4_request" },
      {"x-amz-algorithm": "AWS4-HMAC-SHA256" }
    ]
  }
POLICY
}

function check_s3_file()
{
  RES_TXT=$(curl -s --head https://${BUCKET}.${SERVICE}.${DOMAIN}/${DES_FILE} 2>&1)
  RES=$(echo "${RES_TXT}" | grep '^HTTP' | head -1 | cut -d' ' -f2)
  if [ "${RES}" != "200" ] ; then
    echo "${RES_TXT}"
    echo "Error: https://${BUCKET}.${SERVICE}.${DOMAIN}/${DES_FILE} file does not exist."
    exit 1
  fi
}

CREDENTIALS="${HOME}/.aws/credentials"
BUCKET="cmsrep"
REGION="us"
SRC_FILE=""
DES_FILE=""
ACL="public-read"
MIME=""
SERVICE="s3"
DOMAIN="cern.ch"
CHK_EXISTS=false
while [[ $# -gt 0 ]] ; do
  opt=$1; shift
  case $opt in
    -s|--src)       SRC_FILE="$1"; shift ;;
    -d|--des)       DES_FILE="$1"; shift ;;
    -a|--acl)       ACL="$1"; shift ;;
    -m|--mime)      MIME="$1"; shift ;;
    -r|--region)    RIGION="$1"; shift ;;
    -b|--bucket)    BUCKET="$1"; shift ;;
    -s|--service)   SERVICE="$1"; shift ;;
    -D|--domain)    DOMAIN="$1"; shift ;;
    -e|--exists)    CHK_EXISTS=true;;
    --debug)        set -x;;
    -h|--help) usage 0;;
    *) usage ;;
  esac
done

if [ "$SRC_FILE" = "" ] ; then
  echo "Error: Missing source file name/path."
  usage 1
fi
[ "${DES_FILE}" = "" ] && DES_FILE="${SRC_FILE}"
DES_FILE=$(echo -n "$DES_FILE" | sed "s|^/*||;s|\/$|\/$(basename $SRC_FILE)|")

#Checking for file in S3
if $CHK_EXISTS ; then
  check_s3_file
  exit 0
fi

#Upload local file to S3
[ "$MIME" = "" ] && MIME=$(guess_mime $SRC_FILE)

if [ ! -e "$SRC_FILE" ] ; then
  echo "Error: No such file: $SRC_FILE"
  usage 1
fi
SRC_MD5=$(openssl md5 -binary "$SRC_FILE" | openssl base64)
CDATE=$(date -u +%Y%m%dT%H%M%SZ)
EXP_DATE=$(date -d tomorrow +%Y-%m-%d)
EXP_DATE_STR=$(printf $EXP_DATE | sed 's/-//g')

[ -f "${CREDENTIALS}" ] && eval $(grep '^[a-z]' ${CREDENTIALS} | grep '=' | sed 's| ||g')
[ "${aws_secret_access_key}" = "" ] && echo "Error: aws_secret_access_key not set in ${CREDENTIALS} file" && exit 1
[ "${aws_access_key_id}" = ""     ] && echo "Error: aws_access_key_id not set in ${CREDENTIALS} file" && exit 1

signature_string=$(get_signature_string)
singature=$(hmac_sha256 "key:AWS4${aws_secret_access_key}" "$EXP_DATE_STR")
singature=$(hmac_sha256 "hexkey:${singature}" "$REGION")
singature=$(hmac_sha256 "hexkey:${singature}" "$SERVICE")
singature=$(hmac_sha256 "hexkey:${singature}" "aws4_request")
singature=$(hmac_sha256 "hexkey:${singature}" "${signature_string}")
curl_opts="-F X-Amz-Credential=${aws_access_key_id}/${EXP_DATE_STR}/${REGION}/${SERVICE}/aws4_request \
           -F X-Amz-Algorithm=AWS4-HMAC-SHA256 \
           -F X-Amz-Signature=${singature} \
           -F X-Amz-Date=${CDATE}"

echo "Uploading: $SRC_FILE ($MIME) to $BUCKET:$DES_FILE"
curl -s -F key=$DES_FILE -F acl=$ACL \
    $curl_opts                       \
    -F "Policy=${signature_string}"  \
    -F "Content-MD5=${SRC_MD5}"      \
    -F "Content-Type=${MIME}"        \
    -F "file=@${SRC_FILE}"           \
    https://${BUCKET}.${SERVICE}.${DOMAIN}/

check_s3_file
echo "$SRC_FILE successfully uploaded to backet $BUCKET as $DES_FILE."
