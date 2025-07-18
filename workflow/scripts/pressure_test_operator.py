import time, os
import logging
from evalscope.perf.main import run_perf_benchmark
from evalscope.perf.arguments import Arguments
import json
import sys
from to_mysql import DatabaseArgs, save_benchmark_results_to_db

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    SYSTEM_CONFIG_PATH = "/etc/system-config"
    STATUS_CODE_FILE = '/tmp/status_code'

    def read_system_config(param_name, default_value=''):
        file_path = os.path.join(SYSTEM_CONFIG_PATH, param_name)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    return content if content else default_value
            except Exception as e:
                print(f"Error reading {file_path}: {e}. Returning default value.")
        return default_value

    try:
        release_name = os.environ['RELEASE_NAME']
        configs_json_str = os.environ['CONFIGS_JSON']
        pre_status = os.environ['PRE_STATUS']
        values_yaml = os.environ['VALUES_YAML']
    except KeyError as e:
        print(f"Error: Missing required environment variable: {e}")
        with open(STATUS_CODE_FILE, "w") as f: f.write("false")
        sys.exit(1)

    url = os.environ.get('LLM_SERVICE', f'http://{release_name}:60000')
    
    with open(STATUS_CODE_FILE, "w") as f: f.write("false")
    if pre_status.lower() == 'false':
        print("pre_status is false, skipping performance test.")
        sys.exit(0)

    try:
        config_data = json.loads(configs_json_str)
    except json.JSONDecodeError as e:
        print(f"Error decoding input JSON: {e}")
        sys.exit(1)

    db_enabled = False
    db_connection_args = None
    db_config_path = os.path.join(SYSTEM_CONFIG_PATH, 'system-config.yaml') # Correct filename
    if os.path.exists(db_config_path):
        try:
            import yaml
            with open(db_config_path, 'r') as f:
                db_config = yaml.safe_load(f).get('database', {})
            
            db_host = db_config.get('host')
            if db_host:
                db_enabled = True
                db_connection_args = DatabaseArgs(
                    db_host=db_host,
                    db_port=db_config.get('port', '3306'),
                    db_name=db_config.get('name', 'db'),
                    db_user=db_config.get('user', 'user'),
                    db_password=db_config.get('password', 'passwd'),
                    db_table_name=db_config.get('table', 'test_table'),
                )
        except (ImportError, yaml.YAMLError, IOError) as e:
            logging.info(f"Could not read or parse database config, DB push disabled: {e}")
            
    if db_enabled:
        logging.info(f"Using Database")
    else:
        logging.info(f"Database disabled")
    test_cfg = config_data.get('test', {})
    deploy_cfg = config_data.get('deploy', {})
    concurrency_list = test_cfg.get('concurrency', [])
    requests = test_cfg.get('requests', 5)
    requests_per_list = [c * requests for c in concurrency_list]
    model = deploy_cfg.get('model', {}).get('name', 'unknown-model')
    dataset = test_cfg.get('dataset', 'random')
    dataset_path = test_cfg.get('dataset_path')
    ISL = test_cfg.get('ISL', 0)
    OSL = test_cfg.get('OSL', 500)
    EOS = test_cfg.get('EOS', True)
    config_data['helm']['values'] = values_yaml

    successful_runs = 0
    for concurrency, num_requests in zip(concurrency_list, requests_per_list):
        logging.info(f"--- Running test for concurrency: {concurrency} with {num_requests} requests ---")
        task_cfg = Arguments(
            model=model, url=url + '/v1/chat/completions', api='openai',
            tokenizer_path=model, parallel=concurrency, number=num_requests,
            dataset=dataset, prefix_length=0, min_prompt_length=ISL,
            max_prompt_length=ISL, extra_args={'ignore_eos': EOS},
        )
        if dataset_path: task_cfg.dataset_path = dataset_path
        if OSL > 0: task_cfg.min_tokens = task_cfg.max_tokens = OSL
        if ISL > 0: task_cfg.min_prompt_length = task_cfg.max_prompt_length = ISL

        try:
            test_start_time = time.time()
            results, percentile_results = run_perf_benchmark(task_cfg)
            test_end_time = time.time()

            if not results:
                logging.warning(f"Test for concurrency {concurrency} produced no results.")
                continue

            logging.info(f"Successfully completed test for concurrency: {concurrency}")
            logging.info(f"Result summary for concurrency {concurrency}: {results}")
            successful_runs += 1  # 仅在完全成功时才计数

        except SystemExit as e:
            if e.code != 0:
                logging.error(f"Test for concurrency {concurrency} failed as the testing library exited with code {e.code}.")
            continue  # 继续下一次循环
        except Exception as e:
            logging.error(f"An unexpected error occurred during the test for concurrency {concurrency}: {e}", exc_info=True)
            continue  # 继续下一次循环

        if db_enabled:
            try:
                save_benchmark_results_to_db(
                    db_args=db_connection_args, percentile_metrics=percentile_results,
                    concurrency=concurrency, num_requests=num_requests,
                    start_timestamp=test_start_time, end_timestamp=test_end_time,
                    static_config=config_data, perf_metrics=results,
                )
            except Exception as e:
                logging.error(f"An error occurred during the save data for concurrency {concurrency}: {e}", exc_info=True)

        time.sleep(15)

    if successful_runs > 0:
        logging.info(f"--- Benchmark job finished with {successful_runs} successful run(s). ---")
        with open(STATUS_CODE_FILE, "w") as f: f.write("true")
        sys.exit(0)
    else:
        logging.error("--- Benchmark job failed. All test runs failed. ---")
        with open(STATUS_CODE_FILE, "w") as f: f.write("false")
        sys.exit(1)

if __name__ == "__main__":
    main()
