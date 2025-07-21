#!/bin/bash

# Script to generate values.yaml for sglang-multi-pd helm chart from JSON input
# Usage: ./generate-values.sh <config.json> [output-values.yaml]

set -e

# Check if input file is provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <config.json> [output-values.yaml]"
    echo "  config.json: Input JSON configuration file"
    echo "  output-values.yaml: Output values.yaml file (default: values.yaml)"
    exit 1
fi

INPUT_JSON="$1"
OUTPUT_YAML="${2:-values.yaml}"

# Check if input file exists
if [ ! -f "$INPUT_JSON" ]; then
    echo "Error: Input file '$INPUT_JSON' not found"
    exit 1
fi

# Validate JSON using jq
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed. Please install jq first."
    exit 1
fi

if ! jq empty "$INPUT_JSON" 2>/dev/null; then
    echo "Error: Invalid JSON format in '$INPUT_JSON'"
    exit 1
fi

# Extract configuration values using jq
MODEL_NAME=$(jq -r '.deploy.model.name' "$INPUT_JSON")
PVC_ENABLED=$(jq -r '.deploy.model.PVC.enable' "$INPUT_JSON")
PVC_NAME=$(jq -r '.deploy.model.PVC.name' "$INPUT_JSON")
LOCAL_ENABLED=$(jq -r '.deploy.model.local.enable' "$INPUT_JSON")
MODEL_PATH=$(jq -r '.deploy.model.path' "$INPUT_JSON")
IMAGE=$(jq -r '.deploy.engine.image' "$INPUT_JSON")
ENGINE_NAME=$(jq -r '.deploy.engine.name' "$INPUT_JSON")
VERSION=$(jq -r '.deploy.engine.version' "$INPUT_JSON")

# PD configuration
PD_ENABLED=$(jq -r '.deploy.pd.enable' "$INPUT_JSON")
PREFILL_REPLICAS=$(jq -r '.deploy.pd.prefill.replicas' "$INPUT_JSON")
PREFILL_TP=$(jq -r '.deploy.pd.prefill.tp' "$INPUT_JSON")
PREFILL_PP=$(jq -r '.deploy.pd.prefill.pp' "$INPUT_JSON")
PREFILL_EP_ENABLED=$(jq -r '.deploy.pd.prefill.ep_enable' "$INPUT_JSON")
PREFILL_ARGS=$(jq -r '.deploy.pd.prefill.args[]' "$INPUT_JSON" | sed 's/^/- /')
PREFILL_ENV=$(jq -r '.deploy.pd.prefill.env[]' "$INPUT_JSON" | sed 's/^/- name: /' | sed 's/=/\n  value: /')

DECODE_REPLICAS=$(jq -r '.deploy.pd.decode.replicas' "$INPUT_JSON")
DECODE_TP=$(jq -r '.deploy.pd.decode.tp' "$INPUT_JSON")
DECODE_PP=$(jq -r '.deploy.pd.decode.pp' "$INPUT_JSON")
DECODE_EP_ENABLED=$(jq -r '.deploy.pd.decode.ep_enable' "$INPUT_JSON")
DECODE_ARGS=$(jq -r '.deploy.pd.decode.args[]' "$INPUT_JSON" | sed 's/^/- /')
DECODE_ENV=$(jq -r '.deploy.pd.decode.env[]' "$INPUT_JSON" | sed 's/^/- name: /' | sed 's/=/\n  value: /')

# Calculate group sizes based on GPU per node and TP/PP
NODE_SIZE=$(jq -r '.metadata.node_size' "$INPUT_JSON")
GPU_PER_NODE=$(jq -r '.metadata.gpu_per_node' "$INPUT_JSON")

# Calculate prefill group size
PREFILL_GPUS=$((PREFILL_TP * PREFILL_PP))
PREFILL_GROUP_SIZE=$(( (PREFILL_GPUS + GPU_PER_NODE - 1) / GPU_PER_NODE ))

# Calculate decode group size
DECODE_GPUS=$((DECODE_TP * DECODE_PP))
DECODE_GROUP_SIZE=$(( (DECODE_GPUS + GPU_PER_NODE - 1) / GPU_PER_NODE ))

# Generate values.yaml
cat > "$OUTPUT_YAML" << EOF
# Generated values.yaml for sglang-multi-pd helm chart
# Generated from: $INPUT_JSON
# Date: $(date)

# Model Configuration
model:
  name: "$MODEL_NAME"
  path: "/data0/$MODEL_NAME"
  pvc:
    enabled: $PVC_ENABLED
    name: "$PVC_NAME"
    path: ""
  local:
    enabled: $LOCAL_ENABLED
    path: "/data0/$MODEL_NAME"

# PD Separation Configuration
pd:
  enabled: $PD_ENABLED
  transferBackend: "mooncake"

# Load Balancer Configuration
loadBalancer:
  replicas: 1
  image: "$IMAGE"
  imagePullPolicy: IfNotPresent
  port: 8000
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      cpu: "2000m"
      memory: "4Gi"
  service:
    type: LoadBalancer
    port: 8000
    loadBalancerIP: ""

# Prefill Configuration
prefill:
  replicas: $PREFILL_REPLICAS
  groupSize: $PREFILL_GROUP_SIZE
  restartPolicy: None
  image: "$IMAGE"
  imagePullPolicy: IfNotPresent
  bootstrapPort: 8998
  resources:
    gpu: $GPU_PER_NODE
  args:
    tpSize: $PREFILL_TP
    ppSize: $PREFILL_PP
    epEnabled: $PREFILL_EP_ENABLED
    memFractionStatic: 0.80
  extraArgs:
$(echo "$PREFILL_ARGS")
  env:
$(echo "$PREFILL_ENV")
  service:
    port: 30000

# Decode Configuration
decode:
  replicas: $DECODE_REPLICAS
  groupSize: $DECODE_GROUP_SIZE
  restartPolicy: None
  image: "$IMAGE"
  imagePullPolicy: IfNotPresent
  resources:
    gpu: $GPU_PER_NODE
  args:
    tpSize: $DECODE_TP
    ppSize: $DECODE_PP
    epEnabled: $DECODE_EP_ENABLED
    memFractionStatic: 0.80
  extraArgs:
$(echo "$DECODE_ARGS")
  env:
$(echo "$DECODE_ENV")
  service:
    port: 30001

# Common Environment Variables
commonEnv:
  - name: NCCL_IB_CUDA_SUPPORT
    value: "1"
  - name: NCCL_IB_DISABLE
    value: "0"
  - name: NCCL_IB_GID_INDEX
    value: "3"
  - name: NCCL_DEBUG
    value: INFO
  - name: GLOO_SOCKET_IFNAME
    value: eth0
  - name: NCCL_SOCKET_IFNAME
    value: eth0
EOF

echo "Successfully generated $OUTPUT_YAML from $INPUT_JSON"
echo "Prefill group size: $PREFILL_GROUP_SIZE (GPUs: $PREFILL_GPUS, per node: $GPU_PER_NODE)"
echo "Decode group size: $DECODE_GROUP_SIZE (GPUs: $DECODE_GPUS, per node: $GPU_PER_NODE)"