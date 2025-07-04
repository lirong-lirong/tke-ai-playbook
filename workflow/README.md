The code is still under development and requires further refinement.

# How to use

```bash
# 创建PVC用于收集报告、创建ServiceAccount用于workflow执行helm，创建看板服务
kubectl apply -f pvc-create.yaml && kubectl apply -f workflow-rbac.yaml && helm install llm-dashboard ../helm-charts/dashboard

# 加载测试参数、workflow模版
kubectl apply -f configs/ && kubectl apply -f template/

# 启动工作流
argo submit model-pressure-test.yaml

```
