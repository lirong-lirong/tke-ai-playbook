# RDMA Exporter Chart

This Helm chart deploys the RDMA Exporter, a Prometheus exporter for RDMA device metrics.

## Features

- **Dynamic Counter Discovery**: Automatically discovers and exposes all available hardware counters from `/sys/class/infiniband/<device>/ports/1/counters` and `/sys/class/infiniband/<device>/ports/1/hw_counters`.
- **Bandwidth Calculation**: Calculates receive and transmit bandwidth in bytes/sec based on `port_rcv_data` and `port_xmit_data` counters. It correctly applies the required 4x multiplier to the raw counter values.
- **Helm-based Deployment**: Easily configurable via a Helm chart.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Prometheus Operator (optional, for ServiceMonitor)
- Nodes with RDMA hardware and the `/sys/class/infiniband` directory populated.

## Installation

To install the chart with the release name `my-release`:

```bash
helm repo add [repo-name] [repo-url] # Add your chart repository
helm install my-release [repo-name]/rdma-exporter
```

## Configuration

| Parameter                  | Description                                                                                                                            | Default                                                 |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `image.repository`         | Image repository                                                                                                                       | `rdma-exporter`                                         |
| `image.pullPolicy`         | Image pull policy                                                                                                                      | `IfNotPresent`                                          |
| `image.tag`                | Image tag. Defaults to the chart's `appVersion`.                                                                                       | `1.0.0`                                                 |
| `nodeSelector`             | Node selector to target nodes with RDMA hardware.                                                                                      | `{}` (schedules on all nodes)                           |
| `tolerations`              | List of tolerations for pod assignment.                                                                                                | `[]`                                                    |
| `affinity`                 | Affinity for pod assignment.                                                                                                           | `{}`                                                    |
| `service.port`             | The port for the metrics endpoint.                                                                                                     | `9898`                                                  |
| `serviceMonitor.enabled`   | If true, create a ServiceMonitor for the Prometheus Operator.                                                                          | `false`                                                 |
| `serviceMonitor.namespace` | The namespace where the ServiceMonitor resource will be created.                                                                       | `""` (Release namespace)                                |
| `serviceMonitor.interval`  | Scrape interval for the ServiceMonitor.                                                                                                | `15s`                                                   |
| `resources`                | Pod resource requests and limits.                                                                                                      | `{}`                                                    |
| `securityContext.privileged` | Run the container in privileged mode. Required to access host devices.                                                               | `true`                                                  |
| `env.SYS_PATH`             | Path to the host's /sys directory inside the container.                                                                                | `/host/sys`                                             |
| `env.POLL_INTERVAL`        | The interval in seconds at which the exporter scrapes the counters.                                                                    | `15`                                                    |

## Exposed Metrics

The exporter exposes the following metrics with the labels `device` (e.g., `mlx5_bond_0`) and `node`:

### Calculated Metrics

| Metric                                        | Description                                           |
| --------------------------------------------- | ----------------------------------------------------- |
| `rdma_port_receive_bandwidth_bytes_per_second`  | Receive bandwidth on the RDMA port in bytes/sec.      |
| `rdma_port_transmit_bandwidth_bytes_per_second` | Transmit bandwidth on the RDMA port in bytes/sec.     |

### Dynamic Raw Counters

Additionally, the exporter will dynamically discover and expose all counters found in the `/sys/class/infiniband/<device>/ports/1/counters` and `.../hw_counters` directories. The metric names are automatically generated from the counter file names, prefixed with `rdma_`.

For example, the counter file `port_rcv_errors` will be exposed as the metric `rdma_port_rcv_errors`.
