# SGLang LeaderWorkerSet Helm Chart

用于在 Kubernetes 上部署 SGLang 分布式推理服务的 Helm Chart。

## 先决条件

1. Make sure your K8S cluster has LWS correctly installed. If it hasn’t been set up yet, please follow the [installation instructions](https://github.com/kubernetes-sigs/lws/blob/main/site/content/en/docs/installation/_index.md). **Note:** For LWS versions ≤0.5.x, you must use the Downward API to obtain `LWS_WORKER_INDEX`, as native support for this feature was introduced in v0.6.0.
2. 确保节点上已安装 NVIDIA 驱动和 CUDA

## 安装

```bash
# 创建命名空间
kubectl create namespace sglang

# 安装 Chart
helm install sglang ./sglang-leaderworkerset -n sglang \
  --set model.hostPath="/path/to/your/models" \
  --set resources.leader.gpu=8 \
  --set resources.worker.gpu=8
```

## 配置参数

| 参数                         | 描述                        | 默认值           |
| ---------------------------- | --------------------------- | ---------------- |
| `global.name`              | 部署名称                    | `sglang`       |
| `global.namespace`         | 命名空间                    | `default`      |
| `leaderWorkerSet.replicas` | LeaderWorkerSet 副本数      | `1`            |
| `leaderWorkerSet.size`     | 每组大小 (leader + workers) | `2`            |
| `image.repository`         | SGLang 镜像仓库             | `sglang`       |
| `image.tag`                | 镜像标签                    | `latest`       |
| `model.hostPath`           | 主机模型路径                | `/data/models` |
| `model.mountPath`          | 容器挂载路径                | `/work/models` |
| `resources.leader.gpu`     | Leader GPU 数量             | `8`            |
| `resources.worker.gpu`     | Worker GPU 数量             | `8`            |
| `sglang.tensorParallelism` | 张量并行度                  | `16`           |
| `service.port`             | 服务暴露端口                | `40000`        |

## 访问服务

```bash
# 端口转发
kubectl port-forward -n sglang svc/sglang-leader 40000:40000

# 测试访问
curl http://localhost:40000/v1/chat/completions
```

## 卸载

```bash
helm uninstall sglang -n sglang
```
