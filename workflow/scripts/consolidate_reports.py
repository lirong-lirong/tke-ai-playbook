import os
import json
import re
import requests
from datetime import datetime
import math

def parse_config_from_dirname(dirname):
    """从目录名解析模型配置信息"""
    pattern = r'^(.*?)_([^_]+)_ns(\d+)_gpu(\d+)_tp(\d+)_ep(\d+)(?:_dpAttention(true|false))?$'
    match = re.match(pattern, dirname)
    
    if not match:
        return None
    
    return {
        'model': match.group(1),
        'engine': match.group(2),
        'node_size': int(match.group(3)),
        'gpu_per_node': int(match.group(4)),
        'tp': int(match.group(5)),
        'ep': int(match.group(6)),
        'dp_attention': match.group(7) == 'true'
    }

def parse_params_from_filename(filename):
    """从文件名解析测试参数"""
    pattern = r'bench_(\d+)_(\d+)_c(\d*)'
    match = re.match(pattern, os.path.splitext(filename)[0])
    
    if not match:
        return None
    
    return {
        'ISL': int(match.group(1)),
        'OSL': int(match.group(2)),
        'concurrency': int(match.group(3)) if match.group(3) else 1
    }

def process_workflow(workflow_dir):
    """处理单个工作流目录"""
    workflow_name = os.path.basename(workflow_dir)
    all_results = []
    
    for config_dir in os.listdir(workflow_dir):
        config_path = os.path.join(workflow_dir, config_dir)
        if not os.path.isdir(config_path):
            continue
            
        config = parse_config_from_dirname(config_dir)
        if not config:
            print(f"警告: 无法解析目录名 {config_dir}")
            continue
        
        for file in os.listdir(config_path):
            if not file.startswith('bench_') or not file.endswith('.json'):
                continue
                
            file_path = os.path.join(config_path, file)
            
            params = parse_params_from_filename(file)
            if not params:
                print(f"警告: 无法解析文件名 {file}")
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"错误: 无法读取文件 {file_path} - {e}")
                continue
            
            result = {
                "deployment_config": {
                    "model": config.get('model', ''),
                    "engine": config.get('engine', ''),
                    "node_size": config.get('node_size', 0),
                    "gpu_per_node": config.get('gpu_per_node', 0),
                    "tp": config.get('tp', 0),
                    "ep": config.get('ep', 0)
                },
                "test_config": {
                    "ISL": params.get('ISL', 0),
                    "OSL": params.get('OSL', 0),
                    "concurrency": params.get('concurrency', 0)
                },
                "metrics": {
                    "request_throughput": data.get('request_throughput', 0),
                    "output_throughput": data.get('output_throughput', 0),
                    "total_token_throughput": data.get('total_token_throughput', 0),
                    "mean_ttft_ms": data.get('mean_ttft_ms', 0),
                    "p99_ttft_ms": data.get('p99_ttft_ms', 0),
                    "mean_tpot_ms": data.get('mean_tpot_ms', 0),
                    "p99_tpot_ms": data.get('p99_tpot_ms', 0),
                    "mean_e2el_ms": data.get('mean_e2el_ms', 0),
                    "p99_e2el_ms": data.get('p99_e2el_ms', 0),
                    "completed": data.get('completed', 0),
                    "total_input_tokens": data.get('total_input_tokens', 0),
                    "total_output_tokens": data.get('total_output_tokens', 0)
                },
                "metadata": {
                    "workflow": workflow_name,
                    "date": data.get('date', ''),
                    "file_path": file_path,
                    "timestamp": data.get('timestamp', datetime.utcnow().isoformat())
                }
            }
            
            result["metrics"]["gpu_utilization"] = calculate_gpu_utilization(result)
            result["metrics"]["cost_per_token"] = calculate_cost_per_token(result)
            
            all_results.append(result)
    
    return all_results

def calculate_gpu_utilization(result):
    dep = result["deployment_config"]
    metrics = result["metrics"]
    total_gpus = dep["node_size"] * dep["gpu_per_node"]
    return metrics["total_token_throughput"] / (total_gpus * 1000) if total_gpus > 0 else 0

def calculate_cost_per_token(result):
    dep = result["deployment_config"]
    metrics = result["metrics"]
    hourly_cost_per_node = 10
    tokens_per_hour = metrics["total_token_throughput"] * 3600
    
    if tokens_per_hour > 0:
        return (dep["node_size"] * hourly_cost_per_node) / tokens_per_hour
    return 0

def send_to_dashboard(json_filepath, dashboard_url, api_key):
    if not dashboard_url or not api_key:
        print("警告: Dashboard URL 或 API Key 未配置完整，跳过发送到Dashboard。")
        return False

    if not os.path.exists(json_filepath):
        print(f"错误: 汇总JSON文件不存在: {json_filepath}")
        return False

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    try:
        with open(json_filepath, 'rb') as f:
            print(f"正在将文件 {json_filepath} 发送到 {dashboard_url}...")
            response = requests.post(dashboard_url, headers=headers, data=f, timeout=60)
            response.raise_for_status()
            print(f"成功发送数据到Dashboard: {response.status_code} - {response.text}")
            return True
    except requests.exceptions.Timeout:
        print(f"发送数据到Dashboard超时: 从 {json_filepath} 到 {dashboard_url}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"发送数据到Dashboard失败: {e}")
        return False
    except Exception as e:
        print(f"发送数据到Dashboard时发生未知错误: {e}")
        return False

def save_summary_json(results, output_dir):
    if not results:
        print("没有数据可供保存为摘要JSON。")
        return None
    
    workflow_name = results[0]['metadata']['workflow'] if results else "unknown"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{workflow_name}_summary.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    
    print(f"汇总数据已保存至: {output_file}")
    return output_file

def main():
    # 从环境变量获取工作流目录
    workflow_dir = os.environ['WORKFLOW_DIR']
    if not workflow_dir or not os.path.isdir(workflow_dir):
        print(f"错误: 无效的工作流目录: {workflow_dir}")
        return
    
    output_dir = os.environ.get('OUTPUT_DIR', '/var/argo/outputs')
    dashboard_url = os.environ.get('DASHBOARD_URL')
    dashboard_api_key = os.environ.get('DASHBOARD_API_KEY')
    
    print(f"处理工作流: {os.path.basename(workflow_dir)}")
    
    results = process_workflow(workflow_dir)
    
    if not results:
        print("未找到有效结果")
        return
        
    json_file_path = save_summary_json(results, output_dir) 
    
    if os.getenv('SEND_TO_DASHBOARD', 'true').lower() == 'true' and json_file_path:
        print(f"准备发送汇总文件 {json_file_path} 到 Dashboard 服务...")
        send_to_dashboard(json_file_path, dashboard_url, dashboard_api_key)

if __name__ == "__main__":
    main()
