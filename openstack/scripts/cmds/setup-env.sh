case $1 in
  cmsbuild*)
    export OS_TENANT_ID="dd21c071-cf05-4a5e-8197-0aa0a4d3c8c7"
    export OS_PROJECT_NAME="CMS SDT CI"
    ;;
  *)
    export OS_TENANT_ID="63b9ceb9-4743-42a0-ab89-1a121443ab1d"
    export OS_PROJECT_NAME="CMS SDT Build"
    ;;
esac
export OS_TENANT_NAME="${OS_PROJECT_NAME}"
