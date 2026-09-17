Create: kubectl --context ngt-token create -f session.yaml
        ./create.sh gpu.yaml session-number
        ./create.sh h100.yaml 02
List:   kubectl --context ngt-token get po
Delete: kubectl --context ngt-token delete --force po <session-id>
Connect: ssh <session-id>@ngt.cern.ch

