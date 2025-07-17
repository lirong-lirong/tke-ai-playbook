import time, os
import logging
from evalscope.perf.main import run_perf_benchmark
from evalscope.perf.arguments import Arguments
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict

# --- FIX: Move import to global scope ---
try:
    import mysql.connector
    from mysql.connector import errorcode
except ImportError:
    print("mysql-connector-python is not installed. Skipping database operations.")
    mysql = None
    errorcode = None

# --- Basic Logging Setup ---
logger = logging.getLogger(__name__)

@dataclass
class DatabaseArgs:
    """A dataclass to hold all database connection parameters."""
    db_host: str
    db_port: str
    db_user: str
    db_password: str
    db_name: str
    db_table_name: str = 'evalscope_perf_results'

def _flatten_dict(data: dict, parent_key: str = '', sep: str = '_') -> dict:
    items = []
    for k, v in data.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            if isinstance(v, (list, tuple)):
                v = str(v)
            items.append((new_key, v))
    return dict(items)

def _get_mysql_connection(args: DatabaseArgs):
    if not mysql: return None
    try:
        connection = mysql.connector.connect(
            host=args.db_host, port=args.db_port, user=args.db_user,
            password=args.db_password, database=args.db_name
        )
        return connection
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("Access denied. Check your MySQL username or password.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error(f"Database '{args.db_name}' does not exist.")
        else:
            logger.error(f"Failed to connect to MySQL: {err}", exc_info=True)
        return None

def _get_sql_type(value: Any) -> str:
    """Infers SQL type from a Python value for table creation."""
    if isinstance(value, bool):
        return 'BOOLEAN'
    if isinstance(value, int):
        return 'BIGINT'
    elif isinstance(value, float):
        return 'DOUBLE'
    elif isinstance(value, str) and len(value) < 256:
        return 'VARCHAR(255)'
    else:
        return 'TEXT'

def _restructure_percentiles(percentile_result: dict) -> dict:
    if not percentile_result or 'Percentiles' not in percentile_result:
        return {}
    percentile_labels = [p.replace('%', '') for p in percentile_result.get('Percentiles', [])]
    flat_percentiles = {}
    for key, values in percentile_result.items():
        if key == 'Percentiles':
            continue
        sanitized_key = key.replace(' (s)', '_seconds').replace(' (tok/s)', '_tok_per_s').replace(' ', '_')
        for i, label in enumerate(percentile_labels):
            if i < len(values):
                flat_key = f"p{label}_{sanitized_key}"
                flat_percentiles[flat_key] = values[i]
    return flat_percentiles

def _get_existing_column_info(cursor, table_name: str) -> dict:
    try:
        cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
        return {
            row[0]: row[1].decode('utf-8') if isinstance(row[1], bytearray) else row[1]
            for row in cursor.fetchall()
        }
    except mysql.connector.Error as err:
        if err.errno == 1146:
            return {}
        logger.error(f"Failed to describe table `{table_name}`: {err}", exc_info=True)
        raise

def _save_to_mysql_internal(db_args: DatabaseArgs, data: Dict[str, Any]):
    if not mysql:
        logger.warning("MySQL connector not available. Skipping database operation.")
        return
    table_name = db_args.db_table_name
    connection = _get_mysql_connection(db_args)
    if not connection: return

    try:
        cursor = connection.cursor()
        existing_columns_info = _get_existing_column_info(cursor, table_name)
        existing_columns = set(existing_columns_info.keys())

        if not existing_columns:
            columns_defs = [f"`{col}` {_get_sql_type(val)}" for col, val in data.items()]
            create_table_sql = f"CREATE TABLE `{table_name}` (id INT AUTO_INCREMENT PRIMARY KEY, {', '.join(columns_defs)})"
            logger.info(f"Table `{table_name}` not found. Creating it...")
            cursor.execute(create_table_sql)
        else:
            new_columns = set(data.keys()) - existing_columns
            if new_columns:
                logger.info(f"New columns found: {new_columns}. Adding them...")
                for col in new_columns:
                    col_type = _get_sql_type(data[col])
                    cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{col}` {col_type}")
            for col_name, col_value in data.items():
                if col_name in existing_columns:
                    required_type = _get_sql_type(col_value).upper()
                    current_type = existing_columns_info[col_name].upper()
                    if required_type == 'TEXT' and 'TEXT' not in current_type:
                        logger.warning(f"Column `{col_name}` is `{current_type}` but requires `TEXT`. Modifying column...")
                        cursor.execute(f"ALTER TABLE `{table_name}` MODIFY COLUMN `{col_name}` {required_type}")

        columns_str = '`, `'.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        insert_sql = f"INSERT INTO `{table_name}` (`{columns_str}`) VALUES ({placeholders})"
        cursor.execute(insert_sql, list(data.values()))
        connection.commit()
        logger.info(f"Successfully saved 1 row to MySQL table: `{table_name}`")
    except Exception as e:
        logger.error(f"Failed to save data to MySQL: {e}", exc_info=True)
        if connection.is_connected():
            connection.rollback()
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def save_benchmark_results_to_db(db_args: DatabaseArgs, static_config: Dict[str, Any], concurrency: int, num_requests: int, start_timestamp: float, end_timestamp: float, perf_metrics: Dict[str, Any], percentile_metrics: Dict[str, Any]):
    logger.info("Preparing data for database insertion...")
    flat_static_config = _flatten_dict(static_config)
    flat_percentiles = _restructure_percentiles(percentile_metrics)
    final_data = {
        **flat_static_config,
        **perf_metrics,
        **flat_percentiles,
        'concurrency': concurrency,
        'num_requests': num_requests,
        'start_timestamp': int(start_timestamp),
        'end_timestamp': int(end_timestamp),
    }
    _save_to_mysql_internal(db_args, final_data)

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    CONFIG_MAP_MODEL_PVC_PATH = "/etc/test-parameters"
    STATUS_CODE_FILE = '/tmp/status_code'

    def read_configmap(param_name, default_value=''):
        file_path = os.path.join(CONFIG_MAP_MODEL_PVC_PATH, param_name)
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

    DB_HOST = read_configmap('db_host', default_value=os.getenv('DB_HOST', ''))
    db_enabled = bool(DB_HOST)
    db_connection_args = None
    if db_enabled:
        db_connection_args = DatabaseArgs(
            db_host=DB_HOST,
            db_port=read_configmap('db_port', default_value=os.getenv('DB_PORT', '3306')),
            db_name=read_configmap('db_name', default_value=os.getenv('DB_NAME', 'db')),
            db_user=read_configmap('db_user', default_value=os.getenv('DB_USER', 'user')),
            db_password=read_configmap('db_password', default_value=os.getenv('DB_PASS', 'passwd')),
            db_table_name=read_configmap('db_table', default_value=os.environ.get('DB_TABLE', 'test_table')),
        )

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

        except Exception as e:
            logging.error(f"An error occurred during the test for concurrency {concurrency}: {e}", exc_info=True)
            continue

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

    logging.info("--- Benchmark job finished successfully. ---")
    with open(STATUS_CODE_FILE, "w") as f: f.write("true")

if __name__ == "__main__":
    main()
