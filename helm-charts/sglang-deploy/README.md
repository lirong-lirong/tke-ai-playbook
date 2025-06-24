SGLang deploy

用于在 Kubernetes 上部署 SGLang 分布式推理服务的 Helm Chart。

## 先决条件

1. Make sure your K8S cluster has LWS correctly installed. If it hasn’t been set up yet, please follow the [installation instructions](https://github.com/kubernetes-sigs/lws/blob/main/site/content/en/docs/installation/_index.md). **Note:** For LWS versions ≤0.5.x, you must use the Downward API to obtain `LWS_WORKER_INDEX`, as native support for this feature was introduced in v0.6.0.
2. 确保节点上已安装 NVIDIA 驱动和 CUDA

## 安装

```bash
# 部署模型服务
$ helm install sglang-service ./sglang-deploy -n default \
  --set nodeSize=$NODE_SIZE   \
  --set resources.gpu=$GPU    \
  --set llmConfig.tp=$TP      \
  --set llmConfig.dp=1        \
  --set model.hostPath=$MODEL 
```

## 核心配置参数

| 参数                            | 描述                   | 默认值                                         |
| ------------------------------- | ---------------------- | ---------------------------------------------- |
| leaderWorkerSet.replicas        | 副本数                 | 1                                              |
| leaderWorkerSet.restartPolicy   | 重启策略               | RecreateGroupOnPodRestart                      |
| image                           | 镜像相关配置           |                                                |
| `model.hostPath`              | 主机模型路径           | `/data/models`                               |
| `model.mountPath`             | 容器挂载路径           | `/work/models`                               |
| resourcesPerNode                | 镜像标签               | `latest`                                     |
| nodeSize                        | 节点数（leader+worker) | 2                                              |
| llmConfig.leader                | leader节点服务端口     | 40000                                          |
| `llmConfig.memFractionStatic` | 显存最高占用           | 0.85                                           |
| `llmConfig.tp`                | 张量并行度             | 8                                              |
| `llmConfig.dp`                | 数据并行度             | 2                                              |
| `service.port`                | 服务暴露端口           | `40000`                                      |
| `env`                         | 环境变量相关           | 默认开启RDMA，默认使用eth0作为socket interface |
| service.enable                  | 启用服务               | 3                                              |
| servce.port                     | 服务端口               | 40000                                          |

## 卸载

```bash
$ helm uninstall sglang-service -n sglang
```
