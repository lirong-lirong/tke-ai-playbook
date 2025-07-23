# RDMA Exporter 设计文档

## 1. 需求背景

在进行大规模模型训练或高性能计算时，GPU 节点之间通常使用 RDMA (远程直接内存访问) 技术进行高速网络通信。为了监控压测期间的 RDMA 网络流量和状态，需要开发一个监控组件，该组件能够收集每个节点的 RDMA 网卡指标，并将其暴露给 Prometheus，以便进行统一的监控和告警。

## 2. 总体设计

本项目设计并实现了一个名为 `rdma-exporter` 的 Prometheus 导出器。其核心思想是：

1.  **部署模型**：使用 Kubernetes `DaemonSet` 将 exporter 部署到集群中的每个目标节点上。通过 `nodeSelector` 或 `tolerations` 来精确控制部署范围，确保它只运行在配有 RDMA 网卡的 GPU 节点上。
2.  **指标采集**：Exporter 容器通过 `hostPath` 挂载宿主机的 `/sys` 文件系统，从而能够访问位于 `/sys/class/infiniband/` 下的 RDMA 设备信息。
3.  **动态发现与计算**：Exporter 动态扫描设备 `ports/1/counters` 和 `ports/1/hw_counters` 目录下的所有文件，为每个文件创建一个对应的 Prometheus 指标。更重要的是，它会根据 `port_rcv_data` 和 `port_xmit_data` 的变化率，计算出实时的上下行带宽，提供更直观的监控数据。
4.  **指标暴露**：Exporter 内部运行一个轻量级 Python HTTP 服务器，在 `/metrics` 路径上以 Prometheus 格式暴露所有采集到的原始指标和计算后的带宽指标。
5.  **服务发现**：通过标准的 Kubernetes `Service` 暴露 Exporter 的端口。同时，提供创建 `ServiceMonitor` 资源（CRD）的选项，以无缝对接到 Prometheus Operator，实现指标的自动发现和抓取。
6.  **容器化与分发**：整个应用被打包成一个轻量级的 Docker 镜像，并通过 Helm Chart 进行分发和部署，简化了在不同环境中的安装和配置过程。

## 3. 实现细节

### 3.1. 指标采集器 (rdma-exporter.py)

采集器是一个 Python 脚本，其核心逻辑已经重构以支持动态化和带宽计算。

-   **动态设备与计数器发现**: 
    -   脚本启动时，会扫描 `/sys/class/infiniband` 目录以发现所有 RDMA 设备。
    -   对于每个设备，它会扫描 `ports/1/counters` 和 `ports/1/hw_counters` 两个目录，读取所有可用的计数器文件。
    -   对于每个发现的计数器，脚本会动态创建一个 `prometheus_client.Gauge` 对象并缓存起来。指标名称会经过标准化处理（例如，`port_rcv_errors` -> `rdma_port_rcv_errors`），以符合 Prometheus 的命名规范。
-   **带宽计算**: 
    -   脚本从 `counters` 目录中读取 `port_rcv_data` 和 `port_xmit_data`。
    -   **重要**: 根据 Mellanox 的标准，这些计数器的单位是 “4 bytes”，因此脚本在计算前会将原始值乘以 4，以得到真实的字节数。
    -   脚本在内存中维护一个状态字典 `METRIC_STATE`，用于存储每个设备上一次轮询时的时间戳和所有计数器的值。
    -   带宽计算公式为 `bandwidth_bytes_per_sec = (current_bytes - last_bytes) / delta_time`。
    -   为了处理硬件计数器可能溢出重置的情况，如果字节差值为负，脚本会假定发生了重置，并使用当前的计数值作为本次的增量。
    -   计算出的带宽值通过独立的 `rdma_port_receive_bandwidth_bytes_per_second` 和 `rdma_port_transmit_bandwidth_bytes_per_second` 指标暴露出去。
-   **HTTP 服务**: 脚本使用 `start_http_server` 启动一个 HTTP 服务，监听指定端口（默认为 `9898`）。

### 3.2. 容器化 (Dockerfile)

-   **基础镜像**: 选用 `python:3.9-slim` 作为基础镜像，以保证镜像的轻量化。
-   **依赖安装**: 只安装必要的 `prometheus_client` 库。
-   **运行**: 容器启动时直接执行 `exporter.py` 脚本。

### 3.3. Helm Chart

-   **`values.yaml`**:
    -   增加了 `env.POLL_INTERVAL` 参数，允许用户配置 exporter 内部轮询硬件计数器的频率。
    -   其他参数如 `image`, `nodeSelector`, `securityContext` 等保持不变，提供了灵活的部署选项。
-   **Templates**: `daemonset.yaml` 已更新，将 `POLL_INTERVAL` 从 `values.yaml` 作为环境变量传递给 exporter 容器。

## 4. 使用说明

1.  **自定义 `values.yaml`**: 在部署前，根据你的集群环境修改 `values.yaml` 文件。最重要的配置是 `nodeSelector`。
2.  **安装 Chart**:
    ```bash
    helm install rdma-monitor ./rdma-exporter -n monitoring
    ```
3.  **在 Grafana 中使用**:
    -   **查看带宽**: 你可以直接使用 `rdma_port_receive_bandwidth_bytes_per_second` 和 `rdma_port_transmit_bandwidth_bytes_per_second` 来绘制带宽图表。
    -   **查看原始计数器**: 所有原始硬件计数器都以 `rdma_` 为前缀，例如 `rdma_port_rcv_errors` 或 `rdma_hw_lifespan`。你可以使用 `rate(rdma_port_rcv_errors[5m])` 来观察错误率。
