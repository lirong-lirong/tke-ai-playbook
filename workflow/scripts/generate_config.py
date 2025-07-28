import json
import os
import yaml
import itertools
import math

CONFIG_MAP_MOUNT_PATH = '/etc/test-parameters'
OUTPUT_FILE_PATH = '/tmp/output'

def read_config_from_yaml(file_name, default=None):
    file_path = os.path.join(CONFIG_MAP_MOUNT_PATH, file_name)
    if not os.path.exists(file_path):
        if default is not None: return default
        raise FileNotFoundError(f"Config file not found: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, IOError) as e:
        print(f"Error reading or parsing YAML from {file_path}: {e}")
        if default is not None: return default
        raise

def build_final_config(scenario_combo, common_config):
    # Deep merge common config with scenario-specific config
    # Scenario values take precedence. A bit complex for nested dicts.
    combo = common_config.copy()
    for key, value in scenario_combo.items():
        if isinstance(value, dict) and key in combo and isinstance(combo[key], dict):
            combo[key] = {**combo[key], **value}
        else:
            combo[key] = value

    # --- Extract values from the final merged combo ---
    common_meta = common_config.get('metadata', {})
    scenario_meta = combo.get('metadata', {})
    final_meta = {**common_meta, **scenario_meta}

    node_size = final_meta.get('node_size', 1)
    gpu_per_node = final_meta.get('gpu_per_node', 8)
    gpu_info = final_meta.get('gpu_info', 'unknown')
    
    model_name = combo['model']
    engine_name = combo['engine']
    is_pd_enabled = combo.get('pd_enable', False)
    
    # --- Build metadata.name ---
    scenario_name = combo.get('name', 'unnamed')
    model_short_name = model_name.split('/')[-1]
    workflow_id = f"{model_short_name}-{engine_name}-{scenario_name}".replace('.', '-')

    # --- Determine group_size and helm.name ---
    group_size = 1
    if gpu_per_node > 0:
        if is_pd_enabled:
            pd_config = combo.get('pd', {})
            prefill_conf = pd_config.get('prefill', {})
            decode_conf = pd_config.get('decode', {})
            # Provide defaults for calculation to avoid TypeErrors
            prefill_tp = prefill_conf.get('tp', 1)
            prefill_pp = prefill_conf.get('pp', 1)
            decode_tp = decode_conf.get('tp', 1)
            decode_pp = decode_conf.get('pp', 1)
            group_size = math.ceil(max(prefill_tp * prefill_pp, decode_tp * decode_pp) / gpu_per_node)
        else:
            tp = combo.get('tp', 1)
            pp = combo.get('pp', 1)
            group_size = math.ceil(tp * pp / gpu_per_node)
    
    mode = "single" if group_size == 1 else "multi"
    helm_name = f"{engine_name}-{mode}"
    if is_pd_enabled:
        helm_name += "-pd"

    # --- Build final JSON object, adhering to the spec ---
    common_test_params = common_config.get('test', {})
    scenario_test_params = combo.get('test', {})
    final_test_params = {**common_test_params, **scenario_test_params}

    # Construct the final model path
    base_local_path = combo.get('local_path', '/data/models')
    final_model_path = os.path.join(base_local_path, model_name)

    config = {
        "metadata": {"name": workflow_id, "node_size": node_size, "gpu_per_node": gpu_per_node, "gpu_info": gpu_info},
        "deploy": {
            "model": {
                "name": model_name,
                "PVC": {"enable": combo.get('pvc_enable'), "name": combo.get('pvc_name')},
                "local": {"enable": combo.get('local_enable')},
                "path": final_model_path
            },
            "engine": {"name": engine_name, "version": "", "image": ""},
            "group_size": group_size,
            "pd": {"enable": is_pd_enabled},
            "ep_enable": combo.get('ep_enable', False),
            "args": combo.get('args', []),
            "env": combo.get('env', [])
        },
        "test": {
            "tokenizer": model_name if final_test_params.get('tokenizer_from_model') else final_test_params.get('tokenizer', model_name),
            "ISL": int(final_test_params.get('isl', 0)),
            "OSL": int(final_test_params.get('osl', 500)),
            "dataset": final_test_params.get('dataset', 'random'),
            "dataset_path": final_test_params.get('dataset_path', ''),
            "EOS": final_test_params.get('eos', False),
            "concurrency": final_test_params.get('concurrency', [1, 8, 16]),
            "requests": int(final_test_params.get('requests', 5))
        },
        "helm": {"name": helm_name, "version": "", "values": ""}
    }

    if is_pd_enabled:
        pd_config = combo.get('pd', {})
        prefill_conf = pd_config.get('prefill', {})
        decode_conf = pd_config.get('decode', {})
        # A global ep_enable can be set at the 'pd' level
        pd_ep_enable = pd_config.get('ep_enable', False)

        config["deploy"]["pd"].update({
            "prefill": {
                "replicas": prefill_conf.get('replicas', 1), 
                "tp": prefill_conf.get('tp', 1), 
                "pp": prefill_conf.get('pp', 1), 
                "ep_enable": prefill_conf.get('ep_enable', pd_ep_enable), # prefill specific overrides global
                "args": prefill_conf.get('args', []), 
                "env": prefill_conf.get('env', [])
            },
            
            "decode": {
                "replicas": decode_conf.get('replicas', 1),
                "tp": decode_conf.get('tp', 1),
                "pp": decode_conf.get('pp', 1),
                "ep_enable": decode_conf.get('ep_enable', pd_ep_enable), # decode specific overrides global
                "args": decode_conf.get('args', []),
                "env": decode_conf.get('env', [])
            }
        })
        config["deploy"].update({"replicas": 0, "tp": 0, "pp": 0})
    else:
        config["deploy"].update({"replicas": combo.get('replicas', 1), "tp": combo.get('tp', 1), "pp": combo.get('pp', 1)})
        config["deploy"]["pd"].update({
            "prefill": {"replicas": 0, "tp": 0, "pp": 0, "ep_enable": False, "args": [], "env": []},
            "decode": {"replicas": 0, "tp": 0, "pp": 0, "ep_enable": False, "args": [], "env": []}
        })
        
    return config

def main():
    try:
        config_data = read_config_from_yaml('test-parameters-config.yaml', default={})
    except Exception as e:
        print(f"Error: Could not process config file. {e}")
        return "[]"

    common_config = config_data.get('common', {})
    scenarios = config_data.get('scenarios', [])
    all_test_configs = []

    for scenario in scenarios:
        # Determine the final list of models and engines for this scenario
        if 'model' in scenario and 'engine' in scenario: # Case 3: single string override
            models_to_run = [scenario['model']]
            engines_to_run = [scenario['engine']]
        else: # Case 1 & 2: list-based
            models_to_run = scenario.get('models', common_config.get('models', []))
            engines_to_run = scenario.get('engines', common_config.get('engines', []))

        for model, engine in itertools.product(models_to_run, engines_to_run):
            # Important: The final combo for building the config starts with the scenario,
            # then adds the specific model and engine for this iteration.
            scenario_combo = {**scenario, "model": model, "engine": engine}
            final_config = build_final_config(scenario_combo, common_config)
            all_test_configs.append(final_config)

    return json.dumps(all_test_configs, indent=4)

if __name__ == "__main__":
    final_output = main()
    print(final_output)
    try:
        with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(final_output)
        print(f"Configuration successfully written to {OUTPUT_FILE_PATH}")
    except IOError as e:
        print(f"Error writing to file {OUTPUT_FILE_PATH}: {e}")