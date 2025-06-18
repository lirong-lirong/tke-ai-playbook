#!/usr/bin/env bash

# startup the benchmark program for ’sglang‘
# We plan to unify the benchmark program for all inference engines in the future

# default parameter
: ${BACKEND:=sglang}
: ${MODEL_NAME:=deepseek-r1}
: ${ENDPOINT:=/v1/chat/completions}
: ${DATASET_NAME:=sharegpt}
: ${DATASET_PATH:=ShareGPT_V3_unfiltered_cleaned_split.json}
: ${NUM_PROMPTS:=1000}
: ${HOST:=127.0.0.1}
: ${PORT:=8000}
: ${CONCURRENCY:=64}
: ${RESULT_FILE:=sglang-bench-output}
: ${WARMUP:=100}

echo "Running benchmark for ${BACKEND} with model ${MODEL_NAME} on dataset ${DATASET_NAME} at ${HOST}:${PORT}"

# the benchmark program from https://github.com/sgl-project/sglang/blob/main/python/sglang/bench_serving.py
python3 sglang/python/sglang/bench_serving.py \
    --backend ${BACKEND} \
    --dataset-name ${DATASET_NAME} \
    --dataset-path ${DATASET_PATH} \
    --num-prompts ${NUM_PROMPTS} \
    --max-concurrency ${CONCURRENCY} \
    --output-file ${RESULT_FILE} \
    --host ${HOST} \
    --port ${PORT} \
    --warmup-requests ${WARMUP}
