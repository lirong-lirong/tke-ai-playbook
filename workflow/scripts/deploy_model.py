import json
import os
import subprocess
import sys

def write_and_exit(status_code, message, exit_code=0):
    print(message, file=sys.stderr)
    with open('/tmp/status_code', 'w') as f:
        f.write(str(status_code).lower())
    # Argo will still save outputs if the script exits with 0
    # So we must write to the outputs before exiting.
    if status_code is False and exit_code == 0:
        # Ensure release_name is written to prevent downstream failures
        with open('/tmp/release_name', 'w') as f:
            f.write('failed-release')
        with open('/tmp/values.yaml', 'w') as f:
            f.write('{}')
    sys.exit(exit_code)

def main():
    print('[deploy model]')
    try:
        # 1. Load config from environment variable
        config_json_str = os.environ['CONFIG_JSON']
        chart_path = os.environ['CHART_PATH']
        model_timeout = os.environ['MODEL_TIMEOUT']
        
        config = json.loads(config_json_str)

        # 2. Locate the chart's values generator script
        helm_chart_name = config.get('helm', {}).get('name')
        if not helm_chart_name:
            write_and_exit(False, "[Deploy-Model] Error: helm.name not found in config.")

        full_chart_path = os.path.join(chart_path, helm_chart_name)
        values_generator_script = os.path.join(full_chart_path, 'scripts', 'generate-values.sh')

        if not os.path.isfile(values_generator_script):
            write_and_exit(False, f"[Deploy-Model] Error: Values generator script not found at {values_generator_script}")

        # 3. Execute the script to generate Helm values
        config_tmp_path = '/tmp/config.json'
        with open(config_tmp_path, 'w') as f:
            json.dump(config, f)
        
        result = subprocess.run(
            ['bash', values_generator_script, config_tmp_path],
            capture_output=True, text=True, check=False
        )

        if result.returncode != 0:
            write_and_exit(False, f"[Deploy-Model] Error: generate-values.sh failed with code {result.returncode}\n{result.stderr}")
        
        generated_values = result.stdout
        values_tmp_path = '/tmp/values.yaml'
        with open(values_tmp_path, 'w') as f:
            f.write(generated_values)

        # 4. Sanitize the release name for Helm
        argo_pod_name = os.getenv('ARGO_POD_NAME', 'local-pod')
        release_name = f"{helm_chart_name}-{argo_pod_name[-20:]}"
        with open('/tmp/release_name', 'w') as f:
            f.write(release_name)

        # 5. Execute Helm install
        helm_args = [
            'helm', 'install', release_name, full_chart_path,
            '-f', values_tmp_path,
            '--timeout', f"{model_timeout}s",
            '--atomic'
        ]
        
        print(f"[Deploy-Model] Executing: {' '.join(helm_args)}")
        helm_result = subprocess.run(helm_args, capture_output=True, text=True, check=False)

        if helm_result.returncode != 0:
            write_and_exit(False, f"[Deploy-Model] Error: Helm install failed.\nSTDOUT:\n{helm_result.stdout}\nSTDERR:\n{helm_result.stderr}")

        print(f"[Deploy-Model] Successfully deployed release: {release_name}")
        with open('/tmp/status_code', 'w') as f:
            f.write('true')

    except json.JSONDecodeError as e:
        write_and_exit(False, f"[Deploy-Model] Error: Invalid input JSON. {e}")
    except KeyError as e:
        write_and_exit(False, f"[Deploy-Model] Error: Missing environment variable: {e}")
    except Exception as e:
        write_and_exit(False, f"[Deploy-Model] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
