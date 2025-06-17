FROM ubuntu:24.04

RUN apt-get update && \
	apt-get install -y git python3 python3-venv wget

RUN mkdir /app

# vLLM benchmarks
RUN git clone --depth 1 https://github.com/vllm-project/vllm.git /app/vllm
RUN cd /app && \
	python3 -m venv vllm-venv && \
	. vllm-venv/bin/activate && \
	pip install numpy aiohttp pandas huggingface_hub transformers vllm datasets

# download dataset
RUN cd /app && \
	wget https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered/resolve/main/ShareGPT_V3_unfiltered_cleaned_split.json

# sglang benchmarks
RUN git clone --depth 1 https://github.com/sgl-project/sglang.git /app/sglang
RUN cd /app && \
	python3 -m venv sglang-venv && \
	. sglang-venv/bin/activate && \
	pip install numpy aiohttp pandas huggingface_hub transformers sglang datasets

COPY vllm-bench.sh /app
COPY sglang-bench.sh /app
