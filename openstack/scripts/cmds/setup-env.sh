export OS_PROJECT_DOMAIN_ID=default
export OS_REGION_NAME=cern
export OS_IDENTITY_PROVIDER=sssd
export OS_MUTUAL_AUTH=disabled
export OS_IDENTITY_API_VERSION=3
export OS_AUTH_TYPE=v3fedkerb
export OS_PROTOCOL=kerberos
export OS_AUTH_URL=https://keystone.cern.ch/v3
export OS_VOLUME_API_VERSION=3
export OS_USERNAME=$(whoami)
case $1 in
  cmsbuild*|CMS_SDT_CI)
    export OS_TENANT_ID="dd21c071-cf05-4a5e-8197-0aa0a4d3c8c7"
    export OS_PROJECT_NAME="CMS SDT CI"
    ;;
  vocms-arm*|CMS_Miscellaneous_ARM)
    export OS_TENANT_ID=d9e1127a-94a0-4ced-a3ee-22707eab3449
    export OS_PROJECT_NAME="CMS Miscellaneous ARM"
    ;;
  *)
    export OS_TENANT_ID="63b9ceb9-4743-42a0-ab89-1a121443ab1d"
    export OS_PROJECT_NAME="CMS SDT Build"
    ;;
esac
export OS_TENANT_NAME="${OS_PROJECT_NAME}"
