```bash
# 创建命名空间
kubectl create namespace sglang-prod

# 部署 SGLang 服务
helm install sglang-service ./sglang-leaderworkerset -n sglang-prod \
  --set global.namespace=sglang-prod \
  --set model.hostPath="/data/models/deepseek_v3_moe" \
  --set resources.leader.gpu=8 \
  --set resources.worker.gpu=8 \
  --set sglang.tensorParallelism=16 \
  --set sglang.modelName="deepseek-v3-moe"  # 设置模型名称

# 运行压力测试（必须使用相同的命名空间）
helm install sglang-benchmark ./sglang-benchmark -n sglang-prod \
  --set sglangService.namespace=sglang-prod \
  --set modelName="deepseek-v3-moe" \  # 与SGLang部署中的模型名称一致
  --set numPrompts=500

```