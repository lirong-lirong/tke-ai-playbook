#!/bin/bash

echo "=== GPU Node Status Summary ==="
echo

# Get all nodes with GPU capacity
echo "Nodes with GPU capacity:"
kubectl get nodes -o json | jq -r '
  .items[] | 
  select(.status.capacity // {} | has("nvidia.com/gpu")) |
  .metadata.name + ": " + (.status.capacity["nvidia.com/gpu"] // "0") + " GPUs total"
'

echo
echo "Detailed GPU allocation per node:"

# Get GPU usage per node
echo "GPU Usage by Node:"
kubectl get node -o json | jq -r '
  .items[] |
  select(.status.capacity // {} | has("nvidia.com/gpu")) |
  .metadata.name as $node |
  {
    node: $node,
    total_gpus: (.status.capacity["nvidia.com/gpu"] // "0"),
    allocated_gpus: (.status.allocatable["nvidia.com/gpu"] // "0")
  } |
  .node + ": " + .allocated_gpus + "/" + .total_gpus + " GPUs available"
'

echo
echo "Pods using GPU (grouped by node):"

# Get pods using GPU
echo "Active GPU allocations:"
kubectl get pods --all-namespaces -o json | jq -r '
  .items[] |
  select(.spec.containers[].resources.requests // {} | has("nvidia.com/gpu")) |
  {
    namespace: .metadata.namespace,
    pod: .metadata.name,
    node: .spec.nodeName,
    gpu_request: (.spec.containers[].resources.requests["nvidia.com/gpu"] // "0")
  } |
  .node + " | " + .namespace + "/" + .pod + " | " + .gpu_request + " GPUs"
' | sort

echo
echo "=== Summary: Available GPU Capacity by Node ==="

# Calculate actual usage from pods
for node in $(kubectl get nodes -o json | jq -r '.items[] | select(.status.capacity // {} | has("nvidia.com/gpu")) | .metadata.name'); do
  total=$(kubectl get node $node -o json | jq -r '.status.capacity["nvidia.com/gpu"] // "0"')
  
  # Count GPUs actually allocated (sum of all pods on this node)
  allocated=$(kubectl get pods --all-namespaces --field-selector spec.nodeName=$node -o json | 
    jq -r '[.items[] | select(.spec.containers[].resources.requests // {} | has("nvidia.com/gpu")) | .spec.containers[].resources.requests["nvidia.com/gpu"] // "0" | tonumber] | add // 0')
  
  available=$((total - allocated))
  
  echo "$node: $available/$total GPUs available (used: $allocated)"
done