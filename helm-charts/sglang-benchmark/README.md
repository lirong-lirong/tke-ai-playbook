```bash
# 创建命名空间
kubectl create namespace sglang-prod

# 部署 SGLang 服务
helm install sglang-service ./sglang-deploy -n sglang \
	--set model.hostPath="/path/to/Qwen/Qwen3-32B" \
	--set leaderWorkerSet.size=2 \
	--set resources.leader.gpu=8 \
	--set resources.worker.gpu=8 \
	--set llmConfig.tp=4 \
	--set llmConfig.dp=2 \
	--set llmConfig.modelName="Qwen3-32B" \
	--set model.mountPath="/work/models" 

# 运行压力测试（必须使用相同的命名空间）

helm install sglang-benchmark ./sglang-benchmark -n sglang \
	--set modelName="Qwen3-32B" \
	--set numPrompts=1000  \
	--set tokenizer.hostPath="/path/to/tokenizer" \
	--set tokenizer.mountPath=""/work/models"  # 必须和sglang-service的model.mountPath相同，好像是sglang莫名其妙的bug

```
