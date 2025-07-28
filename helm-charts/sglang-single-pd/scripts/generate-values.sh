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

CONFIG_FILE="$1"
# OUTPUT_YAML="${2:-values.yaml}"

# Check if input file exists
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Error: Config file not found at $CONFIG_FILE" >&2
  exit 1
fi

# # Validate JSON using jq
# if ! command -v jq &> /dev/null; then
#     echo "Error: jq is required but not installed. Please install jq first."
#     exit 1
# fi

# if ! jq empty "$CONFIG_FILE" 2>/dev/null; then
#     echo "Error: Invalid JSON format in '$CONFIG_FILE'"
#     exit 1
# fi

# Extract configuration values using jq
MODEL_NAME=$(jq -r '.deploy.model.name' "$CONFIG_FILE")
PVC_ENABLED=$(jq -r '.deploy.model.PVC.enable' "$CONFIG_FILE")
PVC_NAME=$(jq -r '.deploy.model.PVC.name' "$CONFIG_FILE")
LOCAL_ENABLED=$(jq -r '.deploy.model.local.enable' "$CONFIG_FILE")
MODEL_PATH=$(jq -r '.deploy.model.path' "$CONFIG_FILE")
# IMAGE=$(jq -r '.deploy.engine.image' "$CONFIG_FILE")
# ENGINE_NAME=$(jq -r '.deploy.engine.name' "$CONFIG_FILE")
# VERSION=$(jq -r '.deploy.engine.version' "$CONFIG_FILE")

# PD configuration
PD_ENABLED=$(jq -r '.deploy.pd.enable' "$CONFIG_FILE")
PREFILL_REPLICAS=$(jq -r '.deploy.pd.prefill.replicas' "$CONFIG_FILE")
PREFILL_TP=$(jq -r '.deploy.pd.prefill.tp' "$CONFIG_FILE")
PREFILL_PP=$(jq -r '.deploy.pd.prefill.pp' "$CONFIG_FILE")
PREFILL_EP_ENABLED=$(jq -r '.deploy.pd.prefill.ep_enable' "$CONFIG_FILE")
PREFILL_ARGS=$(jq -r '.deploy.pd.prefill.args | .[]? | "- \"\(. | tostring)\""' "$CONFIG_FILE")
PREFILL_ENV=$(jq -r '.deploy.pd.prefill.env | .[]? | "- name: \(. | split("=")[0])\n  value: \"\(. | split("=")[1])\""' "$CONFIG_FILE")
PREFILL_GPU=$((PREFILL_TP * PREFILL_PP))

DECODE_REPLICAS=$(jq -r '.deploy.pd.decode.replicas' "$CONFIG_FILE")
DECODE_TP=$(jq -r '.deploy.pd.decode.tp' "$CONFIG_FILE")
DECODE_PP=$(jq -r '.deploy.pd.decode.pp' "$CONFIG_FILE")
DECODE_EP_ENABLED=$(jq -r '.deploy.pd.decode.ep_enable' "$CONFIG_FILE")
DECODE_ARGS=$(jq -r '.deploy.pd.decode.args | .[]? | "- \"\(. | tostring)\""' "$CONFIG_FILE")
DECODE_ENV=$(jq -r '.deploy.pd.decode.env | .[]? | "- name: \(. | split("=")[0])\n  value: \"\(. | split("=")[1])\""' "$CONFIG_FILE")
DECODE_GPU=$((DECODE_TP * DECODE_PP))

# Calculate group sizes based on GPU per node and TP/PP
NODE_SIZE=$(jq -r '.metadata.node_size' "$CONFIG_FILE")
GPU_PER_NODE=$(jq -r '.metadata.gpu_per_node' "$CONFIG_FILE")
# # Calculate prefill group size
# PREFILL_GPUS=$((PREFILL_TP * PREFILL_PP))
# PREFILL_GROUP_SIZE=$(( (PREFILL_GPUS + GPU_PER_NODE - 1) / GPU_PER_NODE ))

# # Calculate decode group size
# DECODE_GPUS=$((DECODE_TP * DECODE_PP))
# DECODE_GROUP_SIZE=$(( (DECODE_GPUS + GPU_PER_NODE - 1) / GPU_PER_NODE ))

# Generate values.yaml
# cat > "$OUTPUT_YAML" << EOF
cat <<EOF
# Generated values.yaml for sglang-multi-pd helm chart
# Generated from: $CONFIG_FILE
# Date: $(date)

# Model Configuration
model:
  name: "$MODEL_NAME"
  path: "$MODEL_PATH"
  pvc:
    enabled: $PVC_ENABLED
    name: "$PVC_NAME"
    path: "$MODEL_PATH"
  local:
    enabled: $LOCAL_ENABLED
    path: "$MODEL_PATH"

# PD Separation Configuration
pd:
  enabled: $PD_ENABLED
  transferBackend: "mooncake"

# Load Balancer Configuration
loadBalancer:
  replicas: 1
  image: "fanjiankong-bj.tencentcloudcr.com/pengdrumli/sglang-nixl-mooncake:v0.4.8-cu126"
  imagePullPolicy: IfNotPresent
  port: 60000
  resources:
    requests:
      cpu: "5000m"
      memory: "128Gi"
    limits:
      cpu: "5000m"
      memory: "128Gi"
  service:
    type: LoadBalancer
    port: 60000
    loadBalancerIP: ""

# Prefill Configuration
prefill:
  replicas: 1
  groupSize: 1
  restartPolicy: None
  image: "fanjiankong-bj.tencentcloudcr.com/pengdrumli/sglang-nixl-mooncake:v0.4.8-cu126"
  imagePullPolicy: IfNotPresent
  bootstrapPort: 8998
  resources:
    gpu: $PREFILL_GPU
  args:
    tpSize: $PREFILL_TP
    ppSize: $PREFILL_PP
    epEnabled: $PREFILL_EP_ENABLED
    memFractionStatic: 0.80
  extraArgs:
$(echo "$PREFILL_ARGS" | sed 's/^/    /')

  env:
$(echo "$PREFILL_ENV" | sed 's/^/    /')
  service:
    port: 30000

# Decode Configuration
decode:
  replicas: $DECODE_REPLICAS
  groupSize: $DECODE_GROUP_SIZE
  restartPolicy: None
  image: "fanjiankong-bj.tencentcloudcr.com/pengdrumli/sglang-nixl-mooncake:v0.4.8-cu126"
  imagePullPolicy: IfNotPresent
  resources:
    gpu: $DECODE_GPU
  args:
    tpSize: $DECODE_TP
    ppSize: $DECODE_PP
    epEnabled: $DECODE_EP_ENABLED
    memFractionStatic: 0.80
  extraArgs:
$(echo "$DECODE_ARGS" | sed 's/^/    /')
  env:
$(echo "$DECODE_ENV" | sed 's/^/    /')
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