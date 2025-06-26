# data_loader.py
import os
import json
import pandas as pd
import glob
from datetime import datetime, timedelta
import re
from config import Config
import time

def load_all_reports():
    """加载reports目录下的所有JSON报告文件"""
    all_data = []
    report_files = glob.glob(os.path.join(Config.REPORTS_DIR, '*.json'))
    
    for file_path in report_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
                # 如果是单个报告对象，放入列表
                if isinstance(data, dict):
                    data = [data]
                
                # 添加文件路径信息和提取时间戳
                for entry in data:
                    # 确保metadata存在
                    if 'metadata' not in entry:
                        entry['metadata'] = {}
                    
                    # 添加文件路径和加载时间
                    entry['metadata']['file_path'] = file_path
                    # 统一使用 timestamp 作为字段名
                    if 'date' in entry['metadata']:
                        # 将 date 字段转为 timestamp
                        entry['metadata']['timestamp'] = entry['metadata'].pop('date')
                    elif 'timestamp' not in entry['metadata']:
                        # 当都不存在时使用当前时间
                        entry['metadata']['timestamp'] = datetime.now().isoformat()
                    
                    # 从文件路径或metadata中提取时间戳
                    if 'timestamp' not in entry['metadata']:
                        # 尝试从文件名中提取时间戳
                        filename = os.path.basename(file_path)
                        timestamp_match = re.search(r'(\d{8}-\d{6})', filename)
                        if timestamp_match:
                            timestamp_str = timestamp_match.group(1)
                            try:
                                # 格式: YYYYMMDD-HHMMSS
                                timestamp = datetime.strptime(timestamp_str, "%Y%m%d-%H%M%S")
                                entry['metadata']['timestamp'] = timestamp.isoformat()
                            except:
                                entry['metadata']['timestamp'] = datetime.now().isoformat()
                        else:
                            entry['metadata']['timestamp'] = datetime.now().isoformat()
                    
                    # 确保workflow字段存在
                    if 'workflow' not in entry['metadata']:
                        # 尝试从文件路径提取workflow名称
                        workflow_match = re.search(r'reports/([^/]+)/', file_path)
                        if workflow_match:
                            entry['metadata']['workflow'] = workflow_match.group(1)
                        else:
                            entry['metadata']['workflow'] = "unknown-workflow"
                
                all_data.extend(data)
        except Exception as e:
            print(f"Error loading {file_path}: {str(e)}")
    
    return all_data

def flatten_report_data(report_data):
    """展平报告数据结构"""
    flattened = []
    for entry in report_data:
        flat_entry = {}
        
        # 添加配置信息
        for section in ['deployment_config', 'test_config', 'metrics', 'metadata']:
            if section in entry:
                for k, v in entry[section].items():
                    # 特殊处理时间戳字段
                    if any(time_key in k.lower() for time_key in ['timestamp', 'date', 'time']):
                        try:
                            flat_entry[f"{section}_{k}"] = datetime.fromisoformat(v)
                        except:
                            flat_entry[f"{section}_{k}"] = v
                    else:
                        flat_entry[f"{section}_{k}"] = v
        
        flattened.append(flat_entry)
    
    return pd.DataFrame(flattened)

def get_latest_data():
    # 添加缓存机制
    if not hasattr(get_latest_data, "_last_update") or not hasattr(get_latest_data, "_cached_data"):
        # 初始化缓存
        get_latest_data._last_update = 0
        get_latest_data._cached_data = pd.DataFrame()  # 初始化为空的DataFrame
    
    # 检查是否需要刷新（5秒缓存）
    current_time = time.time()
    if get_latest_data._cached_data.empty or (current_time - get_latest_data._last_update) > 5:
        try:
            # 实际加载数据
            # report_files = glob.glob(os.path.join(Config.REPORTS_DIR, '*.json'))
            # if report_files:
                # 查找最新修改的文件
                # latest_file = max(report_files, key=os.path.getmtime)
                # 仅当文件发生变化时才重新加载
                # if os.path.getmtime(latest_file) > get_latest_data._last_update:
            data = load_all_reports()
            if data:  # 确保有数据
                new_df = flatten_report_data(data)
                if not new_df.empty:
                    get_latest_data._cached_data = new_df
                    get_latest_data._last_update = current_time
            # 如果没有报告文件，保持空的DataFrame
        except Exception as e:
            print(f"数据加载错误: {str(e)}")
            # 出错时返回空的DataFrame
            get_latest_data._cached_data = pd.DataFrame()
    
    return get_latest_data._cached_data