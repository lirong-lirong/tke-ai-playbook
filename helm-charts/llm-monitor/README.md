# LLM Monitor - Enhanced GPU Monitoring / 增强版GPU监控

This helm chart provides comprehensive GPU monitoring using **kube-prometheus-stack** (merged from prometheus-only) with DCGM Exporter integration.

此Helm Chart提供全面的GPU监控，使用**kube-prometheus-stack**（从prometheus-only合并）与DCGM Exporter集成。

## Overview / 概述

This chart now uses **kube-prometheus-stack** (v58.1.0) instead of the basic Prometheus server, providing:

此Chart现在使用**kube-prometheus-stack**（v58.1.0）代替基础Prometheus服务器，提供：

- Full Prometheus Operator with advanced features / 完整的Prometheus Operator与高级功能
- Custom image registry support for offline installation / 支持自定义镜像仓库用于离线安装
- Enhanced ServiceMonitor configuration / 增强的ServiceMonitor配置
- Better GPU metrics collection and management / 更好的GPU指标收集和管理
- All features from prometheus-only are now integrated / 已集成prometheus-only的所有功能

## Components / 组件

- **kube-prometheus-stack**: Full Prometheus stack with operator / 完整的Prometheus堆栈与Operator
- **dcgm-exporter**: NVIDIA GPU metrics collection / NVIDIA GPU指标收集
- **grafana**: Visualization (optional) / 可视化（可选）

## Quick Start / 快速开始

### 1. Installation / 安装

```bash
# Install with default configuration / 使用默认配置安装
helm install llm-monitor ./llm-monitor

# Install with custom values / 使用自定义配置安装
helm install llm-monitor ./llm-monitor -f values.yaml
```

### 2. Access Prometheus / 访问Prometheus

```bash
# Get service IP / 获取服务IP
kubectl get svc llm-monitor-kube-prometheus-stack-prometheus

# Port forward for local access / 本地端口转发访问
kubectl port-forward svc/llm-monitor-kube-prometheus-stack-prometheus 9090:9090
```

### 3. Verify GPU Metrics / 验证GPU指标

Go to Prometheus UI at `http://localhost:9090` and try these queries:

访问Prometheus界面 `http://localhost:9090` 并尝试以下查询：

```promql
# GPU Utilization / GPU利用率
DCGM_FI_DEV_GPU_UTIL

# Memory Usage / 显存使用
DCGM_FI_DEV_FB_USED

# Temperature / 温度
DCGM_FI_DEV_GPU_TEMP

# Power Usage / 功耗
DCGM_FI_DEV_POWER_USAGE
```

## Configuration / 配置

### GPU Monitoring Features / GPU监控功能

The chart automatically configures:

此Chart自动配置：

- DCGM exporter discovery across all namespaces / 跨所有命名空间的DCGM导出器发现
- 5-second scrape interval for GPU metrics / GPU指标5秒抓取间隔
- ServiceMonitor for pushgateway compatibility / pushgateway兼容性的ServiceMonitor
- Persistent storage (50Gi) for metrics retention / 指标保留的持久存储（50Gi）

### Image Registry (Offline Support) / 镜像仓库（离线支持）

All images use the private registry:

所有镜像使用私有仓库：

- `fanjiankong-bj.tencentcloudcr.com/pengdrumli/prometheus-operator:v0.73.0`
- `fanjiankong-bj.tencentcloudcr.com/pengdrumli/prometheus:v2.51.2`
- `fanjiankong-bj.tencentcloudcr.com/pengdrumli/kube-webhook-certgen:v20221220-controller-v1.5.1-58-g787ea74b6`

## Migration from prometheus-only / 从prometheus-only迁移

This chart now **includes all prometheus-only features** and **supersedes** the prometheus-only chart. Users should migrate to llm-monitor for complete GPU monitoring.

此Chart现在**包含所有prometheus-only功能**并**取代**prometheus-only Chart。用户应迁移到llm-monitor以获得完整的GPU监控。

### Key Improvements / 关键改进

1. **Enhanced Prometheus**: kube-prometheus-stack instead of basic prometheus server
   **增强的Prometheus**：使用kube-prometheus-stack代替基础prometheus服务器
2. **Better GPU Discovery**: Automatic DCGM exporter detection
   **更好的GPU发现**：自动DCGM导出器检测
3. **Offline Support**: All images from private registry
   **离线支持**：所有镜像来自私有仓库
4. **Advanced Configuration**: Full Prometheus operator features
   **高级配置**：完整的Prometheus operator功能
5. **Storage**: 50Gi persistent storage vs 10Gi
   **存储**：50Gi持久存储对比10Gi

## Service Configuration / 服务配置

- **Prometheus**: LoadBalancer on port 9090 / 端口9090的LoadBalancer
- **Grafana**: LoadBalancer on port 80 (if enabled) / 端口80的LoadBalancer（如果启用）
- **Pushgateway**: LoadBalancer on port 9091 / 端口9091的LoadBalancer
- **DCGM Exporter**: ClusterIP on port 9400 / 端口9400的ClusterIP

## Troubleshooting / 故障排除

### Check Targets / 检查目标
```bash
kubectl port-forward svc/llm-monitor-kube-prometheus-stack-prometheus 9090:9090
# Visit: http://localhost:9090/targets
# 访问：http://localhost:9090/targets
```

### Verify DCGM Exporter / 验证DCGM导出器
```bash
kubectl get pods -A | grep dcgm-exporter
kubectl get servicemonitor -A | grep dcgm
```

### GPU Node Configuration / GPU节点配置

To ensure DCGM exporter runs only on GPU nodes:

确保DCGM导出器仅在GPU节点上运行：

```yaml
# In values.yaml / 在values.yaml中
dcgm-exporter:
  nodeSelector:
    nvidia-device-enable: "enable"
```

### Common Issues / 常见问题

1. **No GPU metrics found**: Check if nodes have GPU labels
   **找不到GPU指标**：检查节点是否有GPU标签
2. **ServiceMonitor not discovered**: Verify Prometheus serviceMonitorSelector
   **ServiceMonitor未被发现**：验证Prometheus的serviceMonitorSelector
3. **Images not pulling**: Check private registry access
   **镜像拉取失败**：检查私有仓库访问权限

## Uninstallation / 卸载

```bash
helm uninstall llm-monitor
```

## Advanced Configuration / 高级配置

### Custom Scrape Intervals / 自定义抓取间隔

```yaml
# In values.yaml / 在values.yaml中
kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      additionalServiceMonitors:
        - name: "dcgm-exporter"
          endpoints:
            - port: "metrics"
              interval: "1s"  # Custom interval / 自定义间隔
```

### Multiple GPU Types / 多种GPU类型

```yaml
# Add custom labels for different GPU types / 为不同GPU类型添加自定义标签
dcgm-exporter:
  extraArgs:
    - "--collectors=/etc/dcgm-exporter/default-counters.csv"
    - "--kubernetes-gpu-id-type=uid"
```

## Performance Tuning / 性能调优

### Storage Optimization / 存储优化

```yaml
kube-prometheus-stack:
  prometheus:
    prometheusSpec:
      retention: "30d"  # Keep 30 days of data / 保留30天数据
      storageSpec:
        volumeClaimTemplate:
          spec:
            resources:
              requests:
                storage: 100Gi  # Increase storage / 增加存储
```

### Resource Limits / 资源限制

```yaml
# Set appropriate resource limits / 设置适当的资源限制
dcgm-exporter:
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 256Mi
```

This chart now provides **complete GPU monitoring** with all prometheus-only features integrated.

此Chart现在提供**完整的GPU监控**，已集成所有prometheus-only功能。