# llm-monitor

本 Chart 用于提供一个包含 GPU 和 RDMA 监控的完整监控解决方案。

## 组件

- **kube-prometheus-stack**: 完整的 Prometheus 技术栈，包含 Prometheus Operator。
- **dcgm-exporter**: 用于采集 NVIDIA GPU 指标。
- **rdma-exporter**: 用于采集 RDMA (Infiniband) 网卡指标。
- **grafana**: 用于指标的可视化，并预置了 GPU 和 RDMA 的监控面板。

## 安装

```bash
kubectl create ns monitor
helm -n monitor install llm-monitor -f values.yaml .
```

## 使用

### 访问 prometheus

```bash
PROM_IP=$(kubectl -n monitor get svc | grep prometheus-server | awk '{print $4}')
echo "访问 'http://${PROM_IP}' 查看 prometheus"
```

### 访问 grafana

```bash
GRAFANA_HOST=$(kubectl -n monitor get svc | grep grafana | awk '{print $4}')
GRAFANA_PASSWD=$(kubectl -n monitor get secret llm-monitor-grafana -o jsonpath="{.data.admin-password}" | base64 --decode)
echo "访问 'http://${GRAFANA_HOST}' 查看 grafana"
echo "账号: 'admin'"
echo "密码: '${GRAFANA_PASSWD}'"
```
