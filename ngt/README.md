Create: kubectl create -f session.yaml
        ./create.sh gpu.yaml session-number
        ./create.sh h100.yaml 02
List:   kubectl get po
Delete: kubectl delete po <session-id>
Connect: ssh <session-id>@ngt.cern.ch

