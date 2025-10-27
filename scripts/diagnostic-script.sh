#!/bin/bash
###
 # @Author: lirong lirongleiyang@163.com
 # @Date: 2025-09-19 17:01:29
 # @LastEditors: lirong lirongleiyang@163.com
 # @LastEditTime: 2025-10-27 20:27:44
 # @FilePath: /tke-ai-playbook/diagnostic-script.sh
 # @Description: 
 # 
 # Copyright (c) 2025 by lirong, All Rights Reserved. 
### 

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "RDMA Exporter 部署问题诊断脚本"
echo "========================================="

# 检查节点是否存在
echo "1. 检查节点是否存在..."
NODE_EXISTS=$(kubectl get node 10.32.5.71 2>/dev/null | wc -l)
if [ "$NODE_EXISTS" -lt 2 ]; then
    echo -e "${RED}❌ 节点 10.32.5.71 不存在${NC}"
    exit 1
else
    echo -e "${GREEN}✅ 节点 10.32.5.71 存在${NC}"
fi

# 检查节点状态
echo -e "\n2. 检查节点状态..."
NODE_STATUS=$(kubectl get node 10.32.5.71 -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
if [ "$NODE_STATUS" == "True" ]; then
    echo -e "${GREEN}✅ 节点状态为 Ready${NC}"
else
    echo -e "${RED}❌ 节点状态不是 Ready${NC}"
fi

# 检查节点标签
echo -e "\n3. 检查节点标签..."
NODE_LABELS=$(kubectl get node 10.32.5.71 --show-labels)
echo "$NODE_LABELS"

# 检查是否有所需的标签
HAS_NVIDIA_LABEL=$(echo "$NODE_LABELS" | grep "nvidia-device-enable=enable" | wc -l)
if [ "$HAS_NVIDIA_LABEL" -gt 0 ]; then
    echo -e "${GREEN}✅ 节点具有 nvidia-device-enable=enable 标签${NC}"
else
    echo -e "${RED}❌ 节点缺少 nvidia-device-enable=enable 标签${NC}"
fi

# 检查 DaemonSet 状态
echo -e "\n4. 检查 rdma-exporter DaemonSet 状态..."
DS_STATUS=$(kubectl get daemonset rdma-exporter -n monitoring 2>/dev/null)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ rdma-exporter DaemonSet 存在${NC}"
    echo "$DS_STATUS"
    
    # 检查期望的 Pod 数量和当前数量
    DESIRED=$(echo "$DS_STATUS" | awk 'NR==2 {print $2}')
    CURRENT=$(echo "$DS_STATUS" | awk 'NR==2 {print $4}')
    
    if [ "$DESIRED" != "$CURRENT" ]; then
        echo -e "${YELLOW}⚠️  期望的 Pod 数量 ($DESIRED) 与当前数量 ($CURRENT) 不匹配${NC}"
        echo -e "\n5. 检查 DaemonSet 详细信息..."
        kubectl describe daemonset rdma-exporter -n monitoring | grep -A 20 "Events:"
    fi
else
    echo -e "${RED}❌ rdma-exporter DaemonSet 不存在${NC}"
fi

# 检查节点污点
echo -e "\n6. 检查节点污点..."
NODE_TAINTS=$(kubectl describe node 10.32.5.71 | grep -A 5 Taints)
echo "$NODE_TAINTS"

# 检查 DaemonSet 的容忍配置
echo -e "\n7. 检查 DaemonSet 容忍配置..."
if kubectl get daemonset rdma-exporter -n monitoring >/dev/null 2>&1; then
    DS_TOLERATIONS=$(kubectl get daemonset rdma-exporter -n monitoring -o jsonpath='{.spec.template.spec.tolerations}')
    echo "$DS_TOLERATIONS"
else
    echo "DaemonSet 不存在"
fi

echo -e "\n========================================="
echo "诊断完成"
echo "========================================="

# 提供解决建议
echo -e "\n解决建议:"
if [ "$HAS_NVIDIA_LABEL" -eq 0 ]; then
    echo "1. 给节点添加标签:"
    echo "   kubectl label node 10.32.5.71 nvidia-device-enable=enable"
fi

if [ "$NODE_STATUS" != "True" ]; then
    echo "2. 检查节点状态，确保节点处于 Ready 状态"
fi
