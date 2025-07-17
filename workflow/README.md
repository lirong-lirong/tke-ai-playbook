# LLM 模型压力测试工作流

此目录包含一个 Argo Workflow，用于自动化部署、测试和基准测试 LLM 模型。

## 如何运行工作流

请按照以下步骤设置环境并运行压力测试。

### 1. 环境准备

请确保您已安装并配置好以下工具：
- `kubectl`：已连接到您的 Kubernetes 集群。
- `argo` CLI：用于与 Argo Workflows 交互。
- `helm`：用于管理 Helm Chart。

### 2. 创建基础资源

首先，创建工作流所需的持久化存储和服务账户。

```bash
# 为测试报告创建 PVC，并为工作流创建 ServiceAccount
kubectl apply -f pvc-create.yaml
kubectl apply -f workflow-rbac.yaml

# (可选) 安装用于展示测试结果的看板
helm install llm-dashboard ../helm-charts/dashboard
```

### 3. 应用 Kustomize 配置

接下来，使用 `kustomize` 应用所有 Kubernetes 配置。此命令会创建所有必需的资源，包括一个名为 `workflow-scripts` 的 `ConfigMap`，它包含了所有需要执行的脚本。

**注意**: 必须使用 `kustomize` 来应用配置，因为它会正确地处理 `ConfigMap` 的生成和命名。

```bash
# 应用当前目录下的所有 Kustomize 配置
kubectl apply -k ./
```

此命令也会自动应用 `template/` 目录下的所有 Argo `ClusterWorkflowTemplate` 模板。

### 4. 提交工作流

最后，将主工作流提交给 Argo 执行。

```bash
argo submit model-pressure-test.yaml
```

您可以使用 Argo UI 或 Argo CLI 来监控工作流的进度：

```bash
# 查看工作流列表
argo list

# 查看特定工作流的详细信息
argo get <workflow-name>
```