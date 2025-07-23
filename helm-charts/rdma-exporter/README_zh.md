# RDMA Exporter Chart

本 Helm chart 用于部署 RDMA Exporter，一个为 Prometheus 设计的 RDMA 设备指标导出器。

## 特性

- **动态计数器发现**: 自动发现并暴露 `/sys/class/infiniband/<device>/ports/1/counters` 和 `/sys/class/infiniband/<device>/ports/1/hw_counters` 目录下的所有可用硬件计数器。
- **带宽计算**: 基于 `port_rcv_data` 和 `port_xmit_data` 计数器计算接收和发送带宽（单位：字节/秒）。脚本会正确地将原始计数器的值乘以4来计算真实的字节数。
- **基于 Helm 的部署**: 通过 Helm Chart 轻松配置。

## 前提条件

- Kubernetes 1.19+
- Helm 3.2.0+
- Prometheus Operator (可选, 用于 ServiceMonitor)
- 节点上需有所需的 RDMA 硬件，并且 `/sys/class/infiniband` 目录已正确生成。

## 安装

使用 `my-release` 作为发布名称来安装此 chart：

```bash
helm repo add [repo-name] [repo-url] # 添加你的 chart 仓库
helm install my-release [repo-name]/rdma-exporter
```

## 配置参数

| 参数                       | 描述                                                                 | 默认值                                                |
| -------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------- |
| `image.repository`         | 镜像仓库                                                             | `rdma-exporter`                                       |
| `image.pullPolicy`         | 镜像拉取策略                                                         | `IfNotPresent`                                        |
| `image.tag`                | 镜像标签。默认为 chart 的 `appVersion`。                             | `1.0.0`                                               |
| `nodeSelector`             | 节点选择器，用于指定在哪些节点上部署 (通常是带有 RDMA 硬件的节点)。  | `{}` (调度到所有节点)                                 |
| `tolerations`              | 用于 Pod 分配的容忍度列表。                                          | `[]`                                                  |
| `affinity`                 | 用于 Pod 分配的亲和性设置。                                          | `{}`                                                  |
| `service.port`             | 指标端点的端口。                                                     | `9898`                                                |
| `serviceMonitor.enabled`   | 若为 true, 则为 Prometheus Operator 创建 ServiceMonitor。              | `false`                                               |
| `serviceMonitor.namespace` | ServiceMonitor 资源将被创建在哪个命名空间。                          | `""` (Release 命名空间)                               |
| `serviceMonitor.interval`  | ServiceMonitor 的抓取间隔。                                          | `15s`                                                 |
| `resources`                | Pod 的资源请求和限制。                                               | `{}`                                                  |
| `securityContext.privileged` | 以特权模式运行容器。访问主机设备所必需。                           | `true`                                                |
| `env.SYS_PATH`             | 容器内的主机 /sys 目录路径。                                         | `/host/sys`                                           |
| `env.POLL_INTERVAL`        | Exporter 抓取计数器的间隔（秒）。                                    | `15`                                                  |

## 暴露的指标

Exporter 会暴露以下带有 `device` (例如 `mlx5_bond_0`) 和 `node` 标签的指标：

### 计算指标

| 指标                                          | 描述                                     |
| --------------------------------------------- | ---------------------------------------- |
| `rdma_port_receive_bandwidth_bytes_per_second`  | RDMA 端口的接收带宽（字节/秒）。         |
| `rdma_port_transmit_bandwidth_bytes_per_second` | RDMA 端口的发送带宽（字节/秒）。         |

### 动态原始计数器

此外，Exporter 会动态发现并暴露在 `/sys/class/infiniband/<device>/ports/1/counters` 和 `.../hw_counters` 目录中找到的所有计数器。指标名称由计数器文件名自动生成，并以 `rdma_` 为前缀。

例如，计数器文件 `port_rcv_errors` 将被暴露为 `rdma_port_rcv_errors` 指标。
