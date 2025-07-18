#!/bin/bash
set -e

# This script generates a values.yaml file for the sglang-single Helm chart
# based on a standardized JSON input file.

# Usage: ./generate-values.sh <path_to_config.json>

if [ -z "$1" ]; then
  echo "Usage: $0 <path_to_config.json>" >&2
  exit 1
fi

CONFIG_FILE=$1

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Error: Config file not found at $CONFIG_FILE" >&2
  exit 1
fi

# --- Extract values from JSON using jq ---
MODEL_NAME=$(jq -r '.deploy.model.name // ""' "$CONFIG_FILE")
PVC_ENABLED=$(jq -r '.deploy.model.PVC.enable // false' "$CONFIG_FILE")
PVC_NAME=$(jq -r '.deploy.model.PVC.name // ""' "$CONFIG_FILE")
MODEL_PATH_IN_PVC=$(jq -r '.deploy.model.path // ""' "$CONFIG_FILE")
LOCAL_ENABLED=$(jq -r '.deploy.model.local.enable // false' "$CONFIG_FILE")
LOCAL_PATH=$(jq -r '.deploy.model.path // ""' "$CONFIG_FILE")

REPLICAS=$(jq -r '.deploy.replicas // 1' "$CONFIG_FILE")
# IMAGE=$(jq -r '.deploy.engine.image // "sglang-default-image"' "$CONFIG_FILE")
TP_SIZE=$(jq -r '.deploy.tp // 1' "$CONFIG_FILE")
PP_SIZE=$(jq -r '.deploy.pp // 1' "$CONFIG_FILE")

# Calculate the exact number of GPUs required
REQUIRED_GPUS=$((TP_SIZE * PP_SIZE))

EP_ENABLED=$(jq -r '.deploy.ep_enable // false' "$CONFIG_FILE")
GPU_PER_NODE=$(jq -r '.metadata.gpu_per_node // 1' "$CONFIG_FILE")

ENV_YAML=$(jq -r '.deploy.env | .[]? | "- name: \(. | split("=")[0])\n  value: \"\(. | split("=")[1])\""' "$CONFIG_FILE")
EXTRA_ARGS=$(jq -r '.deploy.args | .[]? | "- \"\(. | tostring)\""' "$CONFIG_FILE")

# --- Generate values.yaml content ---
cat <<EOF
model:
  name: "$MODEL_NAME"
  pvc:
    enabled: $PVC_ENABLED
    name: "$PVC_NAME"
    path: "$MODEL_PATH_IN_PVC"
  local:
    enabled: $LOCAL_ENABLED
    path: "$LOCAL_PATH"

server:
  replicas: $REPLICAS
  image: "ccr.ccs.tencentyun.com/tke-ai-playbook/sglang:nightly"
  imagePullPolicy: IfNotPresent
  resources:
    requests:
      nvidia.com/gpu: $REQUIRED_GPUS
    limits:
      nvidia.com/gpu: $REQUIRED_GPUS
  args:
    tpSize: $TP_SIZE
    ppSize: $PP_SIZE
    epEnabled: $EP_ENABLED
  extraArgs:
$(echo "$EXTRA_ARGS" | sed 's/^/    /')

  env:
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
$(echo "$ENV_YAML" | sed 's/^/    /')

service:
  enabled: true
  type: LoadBalancer
  port: 60000
EOF