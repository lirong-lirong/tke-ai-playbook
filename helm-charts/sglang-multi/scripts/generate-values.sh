#!/bin/bash
set -e

# This script generates a values.yaml file for the sglang-multi Helm chart
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

GROUP_SIZE=$(jq -r '.deploy.group_size // 2' "$CONFIG_FILE")
TP_SIZE=$(jq -r '.deploy.tp // 8' "$CONFIG_FILE")
PP_SIZE=$(jq -r '.deploy.pp // 2' "$CONFIG_FILE")
EP_ENABLED=$(jq -r '.deploy.ep_enable // false' "$CONFIG_FILE")

# Calculate the exact number of GPUs required per pod
if [ "$GROUP_SIZE" -eq 0 ]; then
  echo "Error: group_size cannot be zero." >&2
  exit 1
fi
REQUIRED_GPUS=$((TP_SIZE * PP_SIZE / GROUP_SIZE))

ENV_YAML=$(jq -r '.deploy.env | .[]? | "- name: \(. | split("=")[0])\n  value: \"\(. | split("=")[1])\""' "$CONFIG_FILE")
EXTRA_ARGS=$(jq -r '.deploy.args | .[]? | @sh' "$CONFIG_FILE" | tr '\n' ' ')

# --- Generate values.yaml content ---
cat <<EOF
# Default values for sglang-multi.

leaderWorkerSet:
  replicas: 1
  restartPolicy: RecreateGroupOnPodRestart

image:
  repository: ccr.ccs.tencentyun.com/tke-ai-playbook/sglang
  tag: nightly
  pullPolicy: IfNotPresent

model:
  pvc:
    enabled: $PVC_ENABLED
    name: "$PVC_NAME"
    path: "$MODEL_PATH_IN_PVC"
  local:
    enabled: $LOCAL_ENABLED
    path: "$LOCAL_PATH"
  name: "$MODEL_NAME"

multiNode:
  groupSize: $GROUP_SIZE

server:
  resources:
    gpu: $REQUIRED_GPUS
  args:
    tpSize: $TP_SIZE
    ppSize: $PP_SIZE
    epEnabled: $EP_ENABLED
    memFractionStatic: 0.85
    trustRemoteCode: true
  extraArgs: "$EXTRA_ARGS"
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
    $ENV_YAML

service:
  enabled: true
  type: LoadBalancer
  port: 60000
EOF