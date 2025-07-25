import json
import os
import subprocess
import sys
import yaml

def write_and_exit(status_code, message, exit_code=0):
    """Prints a message, writes status, and exits."""
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

def wait_for_resources(release_name, timeout_seconds):
    """
    Waits for workload resources in a Helm release to become ready.
    This function inspects the release manifest and applies the appropriate
    'kubectl wait' or 'kubectl rollout status' command for each resource.
    """
    print(f"[Deploy-Model] Waiting for resources in release '{release_name}' to become ready...")
    
    # 1. Get the manifest for the release
    try:
        manifest_result = subprocess.run(
            ['helm', 'get', 'manifest', release_name],
            capture_output=True, text=True, check=True
        )
        manifests = yaml.safe_load_all(manifest_result.stdout)
    except (subprocess.CalledProcessError, yaml.YAMLError) as e:
        raise RuntimeError(f"Failed to get or parse manifest for release {release_name}: {e}")

    wait_commands = []
    timeout_str = f"{timeout_seconds}s"

    # 2. Parse manifests to find supported workload resources and build wait commands
    for manifest in manifests:
        if not manifest or 'kind' not in manifest or 'metadata' not in manifest:
            continue

        kind = manifest['kind']
        name = manifest['metadata']['name']
        namespace_arg = f"--namespace {manifest['metadata'].get('namespace')}" if manifest['metadata'].get('namespace') else ""

        command = None
        # For common workloads, 'rollout status' is robust and gives good feedback.
        if kind in ['Deployment', 'StatefulSet', 'DaemonSet']:
            command = f"kubectl rollout status {kind.lower()}/{name} {namespace_arg} --timeout={timeout_str}"
        # For Jobs, we wait for completion.
        elif kind == 'Job':
            command = f"kubectl wait --for=condition=Complete job/{name} {namespace_arg} --timeout={timeout_str}"
        # For LeaderWorkerSet, we wait for the 'Available' condition.
        elif kind == 'LeaderWorkerSet':
            command = f"kubectl wait --for=condition=Available leaderworkerset/{name} {namespace_arg} --timeout={timeout_str}"
        
        if command:
            wait_commands.append(command)

    if not wait_commands:
        print("[Deploy-Model] No supported workload resources found to wait for. Assuming success.")
        return

    # 3. Execute wait commands
    print(f"[Deploy-Model] Found {len(wait_commands)} resources to wait for.")
    for cmd in wait_commands:
        print(f"[Deploy-Model] Executing: {cmd}")
        try:
            # Using shell=True because the command is constructed with arguments.
            # check=True will raise CalledProcessError on non-zero exit codes.
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            print(f"[Deploy-Model] Successfully waited for resource. STDOUT:\n{result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"[Deploy-Model] Error waiting for resource with command: {cmd}", file=sys.stderr)
            print(f"STDOUT: {e.stdout}", file=sys.stderr)
            print(f"STDERR: {e.stderr}", file=sys.stderr)
            # Re-raise the exception to be caught by the main loop for cleanup
            raise e

def main():
    print('[deploy model]')
    release_name = ""
    try:
        # 1. Load config from environment variable
        config_json_str = os.environ['CONFIG_JSON']
        chart_path = os.environ['CHART_PATH']
        model_timeout = int(os.environ['MODEL_TIMEOUT'])
        
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
            write_and_exit(False, f"[Deploy-Model] Error: generate-values.sh failed with code {result.returncode} {result.stderr}")
        
        generated_values = result.stdout
        values_tmp_path = '/tmp/values.yaml'
        with open(values_tmp_path, 'w') as f:
            f.write(generated_values)
        print(generated_values)
        
        # 4. Sanitize the release name for Helm
        argo_pod_name = os.getenv('ARGO_POD_NAME', 'local-pod')
        release_name = f"{helm_chart_name}-{argo_pod_name[-20:]}"
        with open('/tmp/release_name', 'w') as f:
            f.write(release_name)

        # 5. Execute Helm install (without --wait and --atomic)
        helm_args = [
            'helm', 'install', release_name, full_chart_path,
            '-f', values_tmp_path,
            '--timeout', f"{model_timeout}s",
            '--atomic',
            '--wait'
        ]
        
        print(f"[Deploy-Model] Executing: {' '.join(helm_args)}")
        helm_result = subprocess.run(helm_args, capture_output=True, text=True, check=False)

        if helm_result.returncode != 0:
            write_and_exit(False, f"[Deploy-Model] Error: Helm install failed. STDOUT: {helm_result.stdout} STDERR: {helm_result.stderr}")

        print(f"[Deploy-Model] Helm install for release '{release_name}' initiated.")

        # 6. Custom wait logic
        wait_for_resources(release_name, model_timeout)

        print(f"[Deploy-Model] Successfully deployed and verified release: {release_name}")
        with open('/tmp/status_code', 'w') as f:
            f.write('true')

    except (json.JSONDecodeError, KeyError, Exception) as e:
        # This block now handles all errors, including wait failures
        error_message = f"[Deploy-Model] An unexpected error occurred: {e}"
        print(error_message, file=sys.stderr)
        
        # If the release was started, uninstall it (mimicking --atomic)
        if release_name:
            print(f"[Deploy-Model] Cleaning up failed release '{release_name}'...", file=sys.stderr)
            subprocess.run(['helm', 'uninstall', release_name], capture_output=True, text=True)
        
        write_and_exit(False, error_message)

if __name__ == "__main__":
    main()