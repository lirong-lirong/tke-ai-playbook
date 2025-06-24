# helm chart for vllm-benchmark 
经过helm chart 包装的大模型推理引擎性能测试程序，测试程序使用vLLM推理引擎自带的[性能测试程序](https://github.com/vllm-project/vllm/blob/main/benchmarks/benchmark_serving.py)。

## 使用方法

```bash
# 部署模型服务
$ helm install sglang-service ./sglang-deploy -n default \
  --set nodeSize=$NODE_SIZE   \
  --set resources.gpu=$GPU    \
  --set llmConfig.tp=$TP      \
  --set llmConfig.dp=1        \
  --set model.hostPath=$MODEL 

# 部署性能测试程序
$ helm install llm-test ./vllm-benchmark -n default \
  --set config.model=$MODEL_NAME \
  --set config.outputPath=$REPORT_DIR \
  --set tokenizer.hostPath=$TOKENIZER \
  --set serviceInfo.name=$SERVICE_NAME \
  --set config.ISL="(500 1000 3000)" \
  --set config.OSL="(1000 1000 150)"

# 查看测试结果
$ kubectl get pods -n default -o wide | grep llm-test
$ kubectl logs -f llm-test-xxx

......

Starting initial single prompt test run...
Initial test run completed. Starting main benchmark run...
Traffic request rate: inf
Burstiness factor: 1.0 (Poisson process)
Maximum request concurrency: 128
100%|██████████| 1280/1280 [19:25<00:00,  1.10it/s] 
============ Serving Benchmark Result ============
Successful requests:                     1280      
Benchmark duration (s):                  1165.05   
Total input tokens:                      3840000   
Total generated tokens:                  191978    
Request throughput (req/s):              1.10      
Output token throughput (tok/s):         164.78    
Total Token throughput (tok/s):          3460.77   
---------------Time to First Token----------------
Mean TTFT (ms):                          53200.49  
Median TTFT (ms):                        51576.36  
P99 TTFT (ms):                           114574.18 
-----Time per Output Token (excl. 1st token)------
Mean TPOT (ms):                          405.79    
Median TPOT (ms):                        397.25    
P99 TPOT (ms):                           732.05    
---------------Inter-token Latency----------------
Mean ITL (ms):                           400.70    
Median ITL (ms):                         91.17     
P99 ITL (ms):                            856.78    
----------------End-to-end Latency----------------
Mean E2EL (ms):                          113656.41 
Median E2EL (ms):                        110228.95 
P99 E2EL (ms):                           220335.58 
==================================================
```

