FROM ubuntu:24.04

RUN apt-get update && \
	apt-get install -y git python3 python3-venv wget

RUN mkdir /app

# download dataset
RUN cd /app && \
	wget https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered/resolve/main/ShareGPT_V3_unfiltered_cleaned_split.json

# sglang benchmarks
RUN git clone --depth 1 https://github.com/sgl-project/sglang.git /app/sglang
RUN cd /app && \
	python3 -m venv sglang-venv && \
	. sglang-venv/bin/activate && \
	pip install numpy aiohttp pandas datasets pydantic requests tqdm transformers

COPY sglang-bench.sh /app
