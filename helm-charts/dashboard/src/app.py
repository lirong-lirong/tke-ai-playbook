import os
import json
import time
from flask import Flask, request, jsonify, send_file # 导入 send_file
import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_loader import get_latest_data
from config import Config
from io import BytesIO # 导入 BytesIO 用于文件下载

# 创建Flask应用
server = Flask(__name__)

# 创建Dash应用
app = dash.Dash(
    __name__, 
    server=server,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    update_title='加载中...'
)

# 全局数据缓存
global_df = get_latest_data()
if global_df is None:  # 额外的保护措施
    global_df = pd.DataFrame()
last_refresh_time = time.time()

# API端点：接收新报告
@server.route('/api/reports', methods=['POST'])
def receive_report():
    # 验证API密钥
    if request.headers.get('X-API-Key') != Config.API_KEY:
        return jsonify({"error": "Invalid API key"}), 401
    
    # 获取报告数据
    report_data = request.json
    
    # 生成文件名 - 包含工作流名称和时间戳
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # 尝试从报告数据中提取工作流名称
    workflow_name = "unknown-workflow"
    try:
        if isinstance(report_data, dict) and 'metadata' in report_data and 'workflow' in report_data['metadata']:
            workflow_name = report_data['metadata']['workflow']
        elif isinstance(report_data, list) and len(report_data) > 0 and 'metadata' in report_data[0] and 'workflow' in report_data[0]['metadata']:
            workflow_name = report_data[0]['metadata']['workflow']
    except Exception: # 捕获所有异常，确保健壮性
        pass
    
    filename = f"report_{workflow_name}_{timestamp}.json"
    filepath = os.path.join(Config.REPORTS_DIR, filename)
    
    # 保存报告
    try:
        with open(filepath, 'w', encoding='utf-8') as f: # 确保使用 utf-8 编码
            json.dump(report_data, f, indent=2)
        
        global_df = get_latest_data() # 立即重新加载数据
        global last_refresh_time
        last_refresh_time = time.time() # 更新刷新时间
        print(f"新报告已保存到: {filepath}, 数据已刷新。")
        return jsonify({"status": "success", "filepath": filepath}), 200
    except Exception as e:
        print(f"保存报告失败: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 新增的下载原始数据API端点
@server.route('/download-json')
def download_json_data():
    global global_df
    if global_df.empty:
        return jsonify({"error": "No data available to download"}), 404
    
    # 将 DataFrame 转换为 JSON 字符串，orient='records' 生成 JSON 数组
    # force_ascii=False 确保中文字符正确编码
    json_data = global_df.to_json(orient='records', date_format='iso', indent=2, force_ascii=False)
    
    # 创建 BytesIO 对象，模拟文件
    buffer = BytesIO()
    buffer.write(json_data.encode('utf-8')) # 写入 UTF-8 编码的 JSON 数据
    buffer.seek(0) # 将文件指针重置到开头
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"model_performance_data_{timestamp}.json"
    
    return send_file(
        buffer,
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )


# 仪表盘布局
def create_dashboard_layout():
    return dbc.Container([
        dcc.Store(id='data-store', data=global_df.to_json(date_format='iso', orient='split')),
        dcc.Interval(id='data-refresh', interval=Config.DATA_REFRESH_INTERVAL * 1000),
        
        dbc.Row(dbc.Col(html.H1("模型性能分析仪表板", className="text-center my-4"))),
        dbc.Row(dbc.Col(html.Div(id='last-update', className="text-end text-muted small"))),
        
        dbc.Row([
            # 左侧控制面板
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("筛选参数"),
                    dbc.CardBody([
                        html.Div([
                            dbc.Button("刷新数据", id="refresh-btn", color="info", className="me-2"),
                            dbc.Button("重置筛选", id="reset-btn", color="secondary", className="me-2"),
                            # 添加下载按钮
                            dcc.Link(
                                dbc.Button("下载原始数据 (JSON)", id="download-json-btn", color="success"), 
                                href="/download-json", 
                                target="_blank", # 在新标签页中打开以触发下载
                                refresh=True # 强制浏览器重新加载链接以触发下载
                            )
                        ], className="mb-3"),
                        
                        # 工作流和时间筛选
                        html.H6("工作流选择", className="mt-2"),
                        dcc.Dropdown(
                            id="workflow-selector",
                            multi=True
                        ),
                        
                        html.H6("时间范围", className="mt-3"),
                        dcc.DatePickerRange(
                            id='date-range-picker',
                            min_date_allowed=datetime.now() - timedelta(days=365),
                            max_date_allowed=datetime.now() + timedelta(days=1),
                            initial_visible_month=datetime.now(),
                            start_date=datetime.now() - timedelta(days=7),
                            end_date=datetime.now(),
                            display_format='YYYY-MM-DD'
                        ),
                        
                        html.H6("模型选择", className="mt-3"),
                        dcc.Dropdown(
                            id="model-selector",
                            multi=True
                        ),
                        
                        html.H6("推理引擎", className="mt-3"),
                        dcc.Dropdown(
                            id="engine-selector",
                            multi=True
                        ),
                        
                        html.H6("节点配置", className="mt-3"),
                        dcc.RangeSlider(
                            id="node-size-slider",
                            min=1,
                            max=8,
                            step=1,
                            marks={i: str(i) for i in range(1, 9)},
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                        
                        html.H6("GPU/节点", className="mt-3"),
                        dcc.RangeSlider(
                            id="gpu-slider",
                            min=1,
                            max=8,
                            step=1,
                            marks={i: str(i) for i in range(1, 9)},
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                        
                        html.H6("张量并行度 (TP)", className="mt-3"),
                        dcc.RangeSlider(
                            id="tp-slider",
                            min=1,
                            max=8,
                            step=1,
                            marks={i: str(i) for i in range(1, 9)},
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                        
                        html.H6("输入序列长度 (ISL)", className="mt-3"),
                        dcc.RangeSlider(
                            id="isl-slider",
                            min=0,
                            max=10000,
                            step=500,
                            marks={i: str(i) for i in range(0, 10001, 2000)},
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                        
                        html.H6("输出序列长度 (OSL)", className="mt-3"),
                        dcc.RangeSlider(
                            id="osl-slider",
                            min=0,
                            max=2000,
                            step=100,
                            marks={i: str(i) for i in range(0, 2001, 500)},
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                        
                        html.H6("并发数", className="mt-3"),
                        dcc.RangeSlider(
                            id="concurrency-slider",
                            min=1,
                            max=256,
                            step=8,
                            marks={i: str(i) for i in [1, 32, 64, 128, 256]},
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                    ])
                ], className="mb-4"),
                
                dbc.Card([
                    dbc.CardHeader("图表配置"),
                    dbc.CardBody([
                        html.H6("主指标选择", className="mt-2"),
                        dcc.Dropdown(
                            id="primary-metric",
                            options=[
                                {"label": "请求吞吐量 (req/s)", "value": "metrics_request_throughput"},
                                {"label": "输出吞吐量 (tok/s)", "value": "metrics_output_throughput"},
                                {"label": "总token吞吐量", "value": "metrics_total_token_throughput"},
                                {"label": "平均TTFT (ms)", "value": "metrics_mean_ttft_ms"},
                                {"label": "P99 TTFT (ms)", "value": "metrics_p99_ttft_ms"},
                                {"label": "平均TPOT (ms)", "value": "metrics_mean_tpot_ms"},
                                {"label": "P99 TPOT (ms)", "value": "metrics_p99_tpot_ms"},
                                {"label": "平均端到端延迟 (ms)", "value": "metrics_mean_e2el_ms"},
                                {"label": "P99端到端延迟 (ms)", "value": "metrics_p99_e2el_ms"},
                                {"label": "GPU利用率", "value": "metrics_gpu_utilization"},
                                {"label": "每token成本", "value": "metrics_cost_per_token"},
                            ],
                            value="metrics_request_throughput"
                        ),
                        
                        html.H6("X轴依据", className="mt-3"),
                        dcc.Dropdown(
                            id="x-axis",
                            options=[
                                {"label": "并发数", "value": "test_config_concurrency"},
                                {"label": "输入序列长度", "value": "test_config_ISL"},
                                {"label": "输出序列长度", "value": "test_config_OSL"},
                                {"label": "GPU数量", "value": "deployment_config_gpu_per_node"},
                                {"label": "张量并行度", "value": "deployment_config_tp"},
                                {"label": "时间", "value": "metadata_timestamp"},
                                {"label": "工作流", "value": "metadata_workflow"}
                            ],
                            value="test_config_concurrency"
                        ),
                        
                        html.H6("分组依据", className="mt-3"),
                        dcc.Dropdown(
                            id="group-by",
                            options=[
                                {"label": "工作流", "value": "metadata_workflow"},
                                {"label": "模型", "value": "deployment_config_model"},
                                {"label": "引擎", "value": "deployment_config_engine"},
                                {"label": "节点数量", "value": "deployment_config_node_size"},
                                {"label": "输入序列长度", "value": "test_config_ISL"},
                                {"label": "输出序列长度", "value": "test_config_OSL"},
                                {"label": "日期", "value": "metadata_date"}
                            ],
                            value="metadata_workflow"
                        )
                    ])
                ])
            ], md=4),
            
            # 右侧图表区域
            dbc.Col([
                dbc.Tabs([
                    dbc.Tab([
                        dcc.Graph(id="primary-metric-graph", className="mt-3"),
                        dbc.Row([
                            dbc.Col(dcc.Graph(id="secondary-graph-1"), width=6),
                            dbc.Col(dcc.Graph(id="secondary-graph-2"), width=6)
                        ], className="mt-4")
                    ], label="性能分析"),
                    
                    dbc.Tab([
                        dash_table.DataTable(
                            id="data-table",
                            page_size=100,
                            style_table={'overflowX': 'auto', 'height': '70vh', 'overflowY': 'auto'},
                            style_cell={
                                'textAlign': 'left',
                                'padding': '10px',
                                'whiteSpace': 'normal',
                                'height': 'auto',
                                'maxWidth': '200px'
                            },
                            style_header={
                                'backgroundColor': 'rgb(230, 230, 230)',
                                'fontWeight': 'bold',
                                'position': 'sticky',
                                'top': 0
                            },
                            filter_action="native",
                            sort_action="native",
                            sort_mode="multi"
                        )
                    ], label="原始数据"),
                    
                    dbc.Tab([
                        dbc.Row([
                            dbc.Col(dcc.Graph(id="correlation-heatmap"), width=8),
                            dbc.Col(dcc.Graph(id="gpu-utilization-chart"), width=4)
                        ]),
                        dbc.Row([
                            dbc.Col(dcc.Graph(id="throughput-scatter"), width=6),
                            dbc.Col(dcc.Graph(id="latency-boxplot"), width=6)
                        ], className="mt-4")
                    ], label="综合分析"),
                    
                    dbc.Tab([
                        dbc.Row([
                            dbc.Col(dcc.Graph(id="workflow-timeline"), width=12)
                        ]),
                        dbc.Row([
                            dbc.Col(dcc.Graph(id="workflow-throughput"), width=6),
                            dbc.Col(dcc.Graph(id="workflow-latency"), width=6)
                        ], className="mt-4")
                    ], label="工作流分析")
                ])
            ], md=8)
        ])
    ], fluid=True)

app.layout = create_dashboard_layout()

# 数据刷新回调
@app.callback(
    [Output('data-store', 'data'),
     Output('last-update', 'children')],
    [Input('data-refresh', 'n_intervals'),
     Input('refresh-btn', 'n_clicks')],  # 添加刷新按钮作为触发源
    prevent_initial_call=False
)
def update_data(n_intervals, refresh_clicks):
    global global_df, last_refresh_time
    
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # 判断触发源是刷新按钮还是定时器
    force_refresh = False
    if triggered_id == 'refresh-btn':
        force_refresh = True
        print("🔄 手动刷新按钮触发")
    
    # 检查是否需要刷新数据，或者如果data-store为空则初始化
    if force_refresh or (time.time() - last_refresh_time > Config.DATA_REFRESH_INTERVAL) or (global_df is None or global_df.empty):
        try:
            # 重新从源头加载数据，确保获取最新数据
            new_df = get_latest_data()
            if new_df is not None:
                global_df = new_df
                last_refresh_time = time.time()
                print(f"🔄 数据已刷新于 {time.strftime('%Y-%m-%d %H:%M:%S')}")
                return global_df.to_json(date_format='iso', orient='split'), f"最后更新: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            else:
                print("⚠️ get_latest_data 返回 None，数据未刷新。")
                return dash.no_update, dash.no_update
        except Exception as e:
            print(f"数据刷新失败: {str(e)}")
            return dash.no_update, dash.no_update # 发生错误时不更新
    
    # 如果不需要刷新，返回现有数据
    return dash.no_update, dash.no_update


# 筛选器重置和更新回调
@app.callback(
    [Output('workflow-selector', 'options'), Output('workflow-selector', 'value'),
     Output('date-range-picker', 'start_date'), Output('date-range-picker', 'end_date'),
     Output('model-selector', 'options'), Output('model-selector', 'value'),
     Output('engine-selector', 'options'), Output('engine-selector', 'value'),
     Output('node-size-slider', 'min'), Output('node-size-slider', 'max'), Output('node-size-slider', 'value'), Output('node-size-slider', 'marks'),
     Output('gpu-slider', 'min'), Output('gpu-slider', 'max'), Output('gpu-slider', 'value'), Output('gpu-slider', 'marks'),
     Output('tp-slider', 'min'), Output('tp-slider', 'max'), Output('tp-slider', 'value'), Output('tp-slider', 'marks'),
     Output('isl-slider', 'min'), Output('isl-slider', 'max'), Output('isl-slider', 'value'), Output('isl-slider', 'marks'),
     Output('osl-slider', 'min'), Output('osl-slider', 'max'), Output('osl-slider', 'value'), Output('osl-slider', 'marks'),
     Output('concurrency-slider', 'min'), Output('concurrency-slider', 'max'), Output('concurrency-slider', 'value'), Output('concurrency-slider', 'marks')],
    [Input('reset-btn', 'n_clicks'),
     Input('data-store', 'data')],
    [State('workflow-selector', 'value'),
     State('date-range-picker', 'start_date'),
     State('date-range-picker', 'end_date'),
     State('model-selector', 'value'),
     State('engine-selector', 'value'),
     State('node-size-slider', 'value'),
     State('gpu-slider', 'value'),
     State('tp-slider', 'value'),
     State('isl-slider', 'value'),
     State('osl-slider', 'value'),
     State('concurrency-slider', 'value')],
    prevent_initial_call=False
)
def update_filter_options(reset_clicks, stored_data,
                          current_workflow_value, current_start_date, current_end_date,
                          current_model_value, current_engine_value,
                          current_node_size_value, current_gpu_value, current_tp_value,
                          current_isl_value, current_osl_value, current_concurrency_value):

    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    is_reset_triggered = (triggered_id == 'reset-btn')

    if stored_data:
        df = pd.read_json(stored_data, orient='split')
        # 确保时间戳列为datetime对象，以便正确获取日期范围
        if 'metadata_timestamp' in df.columns:
            df['metadata_timestamp'] = pd.to_datetime(df['metadata_timestamp'], errors='coerce')
            df = df.dropna(subset=['metadata_timestamp']) # 移除无法解析的行
    else:
        df = pd.DataFrame()

    # 默认日期范围 (当前日期前7天到当前日期)
    default_end_date = datetime.now().date()
    default_start_date = default_end_date - timedelta(days=7)

    # 如果数据为空，返回默认的空状态
    if df.empty:
        return (
            [], [], default_start_date, default_end_date,
            [], [], [], [],
            1, 8, [1, 8], {i: str(i) for i in range(1, 9)},
            1, 8, [1, 8], {i: str(i) for i in range(1, 9)},
            1, 8, [1, 8], {i: str(i) for i in range(1, 9)},
            0, 10000, [0, 10000], {i: str(i) for i in range(0, 10001, 2000)},
            0, 2000, [0, 2000], {i: str(i) for i in range(0, 2001, 500)},
            1, 256, [1, 256], {i: str(i) for i in [1, 32, 64, 128, 256]}
        )

    # --- Dropdown Filters ---
    # Workflows
    unique_workflows = df['metadata_workflow'].unique().tolist() if 'metadata_workflow' in df.columns else []
    workflow_options = [{'label': w, 'value': w} for w in unique_workflows if pd.notna(w)] # 过滤NaN
    workflow_value = unique_workflows # Default to all if reset or initial load
    if not is_reset_triggered and current_workflow_value is not None:
        # Preserve selected values that are still in the new options
        workflow_value = [v for v in current_workflow_value if v in unique_workflows and pd.notna(v)]
        if not workflow_value and unique_workflows:
            workflow_value = unique_workflows

    # Models
    unique_models = df['deployment_config_model'].unique().tolist() if 'deployment_config_model' in df.columns else []
    model_options = [{'label': m, 'value': m} for m in unique_models if pd.notna(m)]
    model_value = unique_models
    if not is_reset_triggered and current_model_value is not None:
        model_value = [v for v in current_model_value if v in unique_models and pd.notna(v)]
        if not model_value and unique_models:
            model_value = unique_models

    # Engines
    unique_engines = df['deployment_config_engine'].unique().tolist() if 'deployment_config_engine' in df.columns else []
    engine_options = [{'label': e, 'value': e} for e in unique_engines if pd.notna(e)]
    engine_value = unique_engines
    if not is_reset_triggered and current_engine_value is not None:
        engine_value = [v for v in current_engine_value if v in unique_engines and pd.notna(v)]
        if not engine_value and unique_engines:
            engine_value = unique_engines

    # --- 日期范围选择器 ---
    start_date_output = default_start_date
    end_date_output = default_end_date

    # 如果有数据，尝试根据数据范围调整日期选择器默认值
    if 'metadata_timestamp' in df.columns and not df['metadata_timestamp'].empty:
        min_date_data = df['metadata_timestamp'].min().date()
        max_date_data = df['metadata_timestamp'].max().date()

        if is_reset_triggered:
            # 重置时，使用数据中的最新7天，或默认7天
            end_date_output = max_date_data
            start_date_output = max(min_date_data, end_date_output - timedelta(days=7))
        elif current_start_date and current_end_date:
            # 尝试保留当前选择
            try:
                start_date_output = datetime.strptime(current_start_date, '%Y-%m-%d').date()
                end_date_output = datetime.strptime(current_end_date, '%Y-%m-%d').date()
                # 确保当前选择的日期在数据范围内，否则调整
                start_date_output = max(min_date_data, start_date_output)
                end_date_output = min(max_date_data, end_date_output)
            except (ValueError, TypeError):
                # 解析失败，退回数据最新7天
                end_date_output = max_date_data
                start_date_output = max(min_date_data, end_date_output - timedelta(days=7))
        else:
            # 初始加载且非重置，使用数据中的最新7天
            end_date_output = max_date_data
            start_date_output = max(min_date_data, end_date_output - timedelta(days=7))
    else:
        # 没有数据，使用默认日期范围
        pass # 已经设置为default_start_date和default_end_date


    # --- 范围滑块 ---
    slider_outputs = []

    # 定义滑块列及其默认/初始范围和步长
    sliders_info = {
        'node-size-slider': {'col': 'deployment_config_node_size', 'default_range': [1, 8], 'step': 1},
        'gpu-slider': {'col': 'deployment_config_gpu_per_node', 'default_range': [1, 8], 'step': 1},
        'tp-slider': {'col': 'deployment_config_tp', 'default_range': [1, 8], 'step': 1},
        'isl-slider': {'col': 'test_config_ISL', 'default_range': [0, 10000], 'step': 500},
        'osl-slider': {'col': 'test_config_OSL', 'default_range': [0, 2000], 'step': 100},
        'concurrency-slider': {'col': 'test_config_concurrency', 'default_range': [1, 256], 'step': 8}
    }

    current_slider_values = {
        'node-size-slider': current_node_size_value,
        'gpu-slider': current_gpu_value,
        'tp-slider': current_tp_value,
        'isl-slider': current_isl_value,
        'osl-slider': current_osl_value,
        'concurrency-slider': current_concurrency_value
    }

    for slider_id, info in sliders_info.items():
        col = info['col']
        default_min, default_max = info['default_range']
        step = info['step']

        # Calculate new min/max based on current data
        if col in df.columns and not df[col].empty:
            data_min = df[col].min()
            data_max = df[col].max()
            # 确保转换成整数，并处理可能存在的NaN
            new_min = int(data_min) if pd.notna(data_min) else default_min
            new_max = int(data_max) if pd.notna(data_max) else default_max
        else:
            new_min = default_min
            new_max = default_max

        # Ensure new_min <= new_max. If data is single value, min/max should be that value.
        if new_min > new_max:
            if col in df.columns and not df[col].empty:
                 # If only one value in the data, set min/max to that value
                 single_val = int(df[col].iloc[0])
                 new_min, new_max = single_val, single_val
            else:
                 new_min, new_max = default_min, default_max # Fallback to default if no data for the column or error


        # 调整滑块的 marks
        marks = {}
        # Modified condition to include 'node-size-slider', 'tp-slider' and 'gpu-slider'
        if slider_id in ['node-size-slider', 'isl-slider', 'osl-slider', 'tp-slider', 'gpu-slider']:
            if col in df.columns and not df[col].empty:
                # 使用数据中存在的唯一数值作为 marks
                unique_values = sorted(df[col].dropna().unique().astype(int).tolist())
                # 只显示一部分 marks 以免过多，但确保min/max在其中
                if len(unique_values) > 10: # 如果唯一值过多，只显示关键点
                    marks_to_show = set()
                    marks_to_show.add(unique_values[0])
                    marks_to_show.add(unique_values[-1])
                    # 尝试均匀选取一些中间值
                    if len(unique_values) > 2:
                        indices = np.linspace(0, len(unique_values) - 1, min(8, len(unique_values))).astype(int)
                        for idx in indices:
                            marks_to_show.add(unique_values[idx])
                    sorted_marks = sorted(list(marks_to_show))
                    for val in sorted_marks:
                        marks[val] = str(val)
                else: # 唯一值不多，全部显示
                    for val in unique_values:
                        marks[val] = str(val)
                
                # 如果数据只有一个值，确保 min/max/value 都设定为这个值
                if len(unique_values) == 1:
                    new_min = unique_values[0]
                    new_max = unique_values[0]
            else:
                # 如果没有数据，回到默认值
                new_min, new_max = default_min, default_max
                marks = {i: str(i) for i in range(default_min, default_max + 1, step if step > 0 else 1)}
        elif slider_id == 'concurrency-slider':
            # 并发数有特定的标记
            standard_marks = [1, 32, 64, 128, 256]
            for i in standard_marks:
                if new_min <= i <= new_max:
                    marks[i] = str(i)
        else:
            # 其他滑块按步长生成标记
            current_val_for_marks = new_min
            while current_val_for_marks <= new_max:
                marks[current_val_for_marks] = str(current_val_for_marks)
                current_val_for_marks += step
            # 确保最大值标记存在
            if new_max not in marks:
                marks[new_max] = str(new_max)
        # 确保最小值标记存在
        if new_min not in marks and new_min in range(default_min, default_max +1): # only add if within original default range
            marks[new_min] = str(new_min)

        # 设置滑块的当前值
        slider_value = [new_min, new_max] # Default to new full range
        if not is_reset_triggered and current_slider_values[slider_id] is not None:
            try:
                # Preserve existing value, clamping to new min/max
                current_low, current_high = current_slider_values[slider_id]
                preserved_low = max(new_min, current_low)
                preserved_high = min(new_max, current_high)
                # Ensure start is not greater than end after clamping
                if preserved_low > preserved_high:
                    slider_value = [new_min, new_max] # Reset if invalid range after clamping
                else:
                    slider_value = [preserved_low, preserved_high]
            except (TypeError, IndexError): # Handle cases where current_val might be malformed
                slider_value = [new_min, new_max]
        
        slider_outputs.extend([new_min, new_max, slider_value, marks])


    return (
        workflow_options, workflow_value,
        start_date_output, end_date_output,
        model_options, model_value,
        engine_options, engine_value,
        *slider_outputs
    )

# 更新图表和数据表
@app.callback(
    [Output('primary-metric-graph', 'figure'),
     Output('secondary-graph-1', 'figure'),
     Output('secondary-graph-2', 'figure'),
     Output('data-table', 'columns'),
     Output('data-table', 'data'),
     Output('correlation-heatmap', 'figure'),
     Output('gpu-utilization-chart', 'figure'),
     Output('throughput-scatter', 'figure'),
     Output('latency-boxplot', 'figure'),
     Output('workflow-timeline', 'figure'),
     Output('workflow-throughput', 'figure'),
     Output('workflow-latency', 'figure')],
    [Input('data-store', 'data'), # 监听数据存储的变化
     Input('workflow-selector', 'value'),
     Input('date-range-picker', 'start_date'),
     Input('date-range-picker', 'end_date'),
     Input('model-selector', 'value'),
     Input('engine-selector', 'value'),
     Input('node-size-slider', 'value'),
     Input('gpu-slider', 'value'),
     Input('tp-slider', 'value'),
     Input('isl-slider', 'value'),
     Input('osl-slider', 'value'),
     Input('concurrency-slider', 'value'),
     Input('primary-metric', 'value'),
     Input('x-axis', 'value'),
     Input('group-by', 'value')]
)
def update_dashboard(stored_data, workflows, start_date, end_date, models, engines, node_size, 
                     gpu_per_node, tp, isl, osl, concurrency, primary_metric, x_axis, group_by):
    
    # 从存储的数据加载DataFrame
    if stored_data:
        df = pd.read_json(stored_data, orient='split')
        # 确保时间戳列是正确的datetime类型
        if 'metadata_timestamp' in df.columns:
            df['metadata_timestamp'] = pd.to_datetime(df['metadata_timestamp'], errors='coerce')
    else:
        df = pd.DataFrame() # 如果没有存储数据，则使用空DataFrame
    
    # 处理空数据集
    if df.empty:
        # 返回空图表占位符和空数据
        empty_fig = px.scatter(title="没有可用数据")
        return (
            empty_fig, empty_fig, empty_fig, # primary, secondary-1, secondary-2
            [], [], # data-table columns, data-table data
            empty_fig, empty_fig, empty_fig, empty_fig, # correlation, gpu, throughput-scatter, latency-boxplot
            empty_fig, empty_fig, empty_fig # workflow-timeline, workflow-throughput, workflow-latency
        )
    
    # 应用筛选条件 - 工作流
    if workflows and len(workflows) > 0:
        df = df[df['metadata_workflow'].isin(workflows)]
    
    # 应用筛选条件 - 时间范围
    if start_date and end_date:
        try:
            # 确保时间列为datetime类型
            df = df[(df['metadata_timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
                    (df['metadata_timestamp'].dt.date <= pd.to_datetime(end_date).date())]
        except Exception as e:
            print(f"时间范围筛选错误: {str(e)}")
    
    # 应用其他筛选条件
    if models and len(models) > 0:
        df = df[df['deployment_config_model'].isin(models)]
    if engines and len(engines) > 0:
        df = df[df['deployment_config_engine'].isin(engines)]
    
    # 应用数值范围筛选，确保列存在且非空
    if 'deployment_config_node_size' in df.columns and not df['deployment_config_node_size'].empty:
        df = df[df['deployment_config_node_size'].between(node_size[0], node_size[1])]
    if 'deployment_config_gpu_per_node' in df.columns and not df['deployment_config_gpu_per_node'].empty:
        df = df[df['deployment_config_gpu_per_node'].between(gpu_per_node[0], gpu_per_node[1])]
    if 'deployment_config_tp' in df.columns and not df['deployment_config_tp'].empty:
        df = df[df['deployment_config_tp'].between(tp[0], tp[1])]
    if 'test_config_ISL' in df.columns and not df['test_config_ISL'].empty:
        df = df[df['test_config_ISL'].between(isl[0], isl[1])]
    if 'test_config_OSL' in df.columns and not df['test_config_OSL'].empty:
        df = df[df['test_config_OSL'].between(osl[0], osl[1])]
    if 'test_config_concurrency' in df.columns and not df['test_config_concurrency'].empty:
        df = df[df['test_config_concurrency'].between(concurrency[0], concurrency[1])]

    # 再次检查空数据集
    if df.empty:
        empty_fig = px.scatter(title="筛选后没有可用数据")
        return (
            empty_fig, empty_fig, empty_fig, # primary, secondary-1, secondary-2
            [], [], # data-table columns, data-table data
            empty_fig, empty_fig, empty_fig, empty_fig, # correlation, gpu, throughput-scatter, latency-boxplot
            empty_fig, empty_fig, empty_fig # workflow-timeline, workflow-throughput, workflow-latency
        )
    
    # 主指标图表
    primary_fig = px.scatter(
        df,
        x=x_axis,
        y=primary_metric,
        color=group_by,
        title=f"性能分析: {primary_metric.split('_')[-1]}",
        hover_data=['metadata_workflow', 'metadata_timestamp']
    )
    primary_fig.update_layout(
        xaxis_title=x_axis.split('_')[-1],
        yaxis_title=primary_metric.split('_')[-1],
        hovermode="closest"
    )
    
    # 次要图表1：吞吐量相关
    if 'metrics_request_throughput' in df.columns and 'metrics_output_throughput' in df.columns:
        throughput_fig = px.scatter(
            df,
            x=x_axis,
            y=['metrics_request_throughput', 'metrics_output_throughput'],
            color=group_by,
            title="吞吐量分析",
            labels={"value": "吞吐量"},
            hover_data=['metadata_workflow', 'metadata_timestamp']
        )
        throughput_fig.update_layout(legend_title="指标")
    else:
        throughput_fig = px.scatter(title="吞吐量数据缺失")
    
    # 次要图表2：延迟相关
    latency_cols = []
    for col in ['metrics_mean_ttft_ms', 'metrics_mean_tpot_ms', 'metrics_mean_e2el_ms']:
        if col in df.columns:
            latency_cols.append(col)
    
    if latency_cols:
        latency_fig = px.scatter(
            df,
            x=x_axis,
            y=latency_cols,
            color=group_by,
            title="延迟分析",
            labels={"value": "延迟 (ms)"},
            hover_data=['metadata_workflow', 'metadata_timestamp']
        )
        latency_fig.update_layout(legend_title="延迟类型")
    else:
        latency_fig = px.scatter(title="延迟数据缺失")
    
    # 数据表格
    columns = [{"name": col, "id": col} for col in df.columns]
    table_data = df.to_dict('records')
    
    # 相关性热力图
    corr_cols = [c for c in df.columns if c.startswith('metrics_') and pd.api.types.is_numeric_dtype(df[c])]
    if len(corr_cols) > 1:
        try:
            corr_df = df[corr_cols].corr(numeric_only=True)
            corr_fig = px.imshow(
                corr_df,
                labels=dict(x="指标", y="指标", color="相关性"),
                text_auto=".2f",
                aspect="auto",
                title="性能指标相关性分析"
            )
        except Exception as e:
            print(f"相关性计算失败: {str(e)}")
            corr_fig = px.scatter(title="相关性计算失败")
    else:
        corr_fig = px.scatter(title="需要至少两个指标来计算相关性")
    
    # GPU利用率图表
    if 'metrics_gpu_utilization' in df.columns:
        gpu_fig = px.scatter(
            df,
            x="test_config_concurrency" if "test_config_concurrency" in df.columns else "metadata_workflow",
            y="metrics_gpu_utilization",
            color="metadata_workflow" if "metadata_workflow" in df.columns else None,
            size="metrics_total_token_throughput" if "metrics_total_token_throughput" in df.columns else None,
            title="GPU利用率分析",
            labels={"y": "GPU利用率"},
            hover_data=["deployment_config_model", "test_config_ISL", "test_config_OSL"]
        )
    else:
        gpu_fig = px.scatter(title="GPU利用率数据缺失")
    
    # 吞吐量散点图
    if 'metrics_request_throughput' in df.columns and 'metrics_output_throughput' in df.columns:
        scatter_fig = px.scatter(
            df,
            x="metrics_request_throughput",
            y="metrics_output_throughput",
            color="metadata_workflow" if "metadata_workflow" in df.columns else None,
            title="请求吞吐量 vs 输出吞吐量",
            labels={
                "metrics_request_throughput": "请求吞吐量 (req/s)",
                "metrics_output_throughput": "输出吞吐量 (tok/s)"
            }
        )
    else:
        scatter_fig = px.scatter(title="吞吐量数据缺失")
    
    # 延迟箱线图
    if latency_cols and 'metadata_workflow' in df.columns:
        latency_df = df.melt(
            id_vars=['metadata_workflow'],
            value_vars=latency_cols,
            var_name='metric',
            value_name='latency'
        )
        box_fig = px.box(
            latency_df,
            x="metadata_workflow",
            y="latency",
            color="metadata_workflow",
            title="不同工作流的延迟分布对比",
            labels={"latency": "延迟 (ms)"}
        )
        box_fig.update_layout(showlegend=False)
    else:
        box_fig = px.scatter(title="延迟数据缺失或工作流数据缺失")
    
    # 工作流时间线
    if 'metadata_timestamp' in df.columns and 'metadata_workflow' in df.columns:
        try:
            timeline_df = df.copy()
            timeline_df['date'] = timeline_df['metadata_timestamp'].dt.date
            timeline_fig = px.timeline(
                timeline_df,
                x_start='date',
                x_end='date',
                y="metadata_workflow",
                color="metadata_workflow",
                title="工作流活动时间线"
            )
            timeline_fig.update_layout(showlegend=False)
        except Exception as e:
            print(f"时间线生成失败: {str(e)}")
            timeline_fig = px.scatter(title="时间线生成失败")
    else:
        timeline_fig = px.scatter(title="工作流或时间数据缺失")
    
    # 工作流吞吐量对比
    if 'metadata_workflow' in df.columns:
        bar_cols = []
        for col in ['metrics_request_throughput', 'metrics_output_throughput', 'metrics_total_token_throughput']:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                bar_cols.append(col)
        
        if bar_cols:
            workflow_throughput_fig = px.bar(
                df,
                x="metadata_workflow",
                y=bar_cols,
                barmode="group",
                title="工作流吞吐量对比",
                labels={"value": "吞吐量"}
            )
        else:
            workflow_throughput_fig = px.scatter(title="吞吐量数据缺失")
    else:
        workflow_throughput_fig = px.scatter(title="工作流数据缺失")
    
    # 工作流延迟对比
    if 'metadata_workflow' in df.columns and not df['metadata_workflow'].empty:
        latency_cols_for_workflow = [
            c for c in df.columns 
            if c.startswith('metrics_') and 
               ('ttft' in c or 'tpot' in c or 'e2el' in c) and
               pd.api.types.is_numeric_dtype(df[c])
        ]
        
        if latency_cols_for_workflow:
            # 计算每个工作流的平均延迟
            latency_data = []
            for workflow in df['metadata_workflow'].unique():
                workflow_data = df[df['metadata_workflow'] == workflow]
                for col in latency_cols_for_workflow:
                    if col in workflow_data.columns:
                        # 计算平均值，处理可能的缺失值
                        mean_value = workflow_data[col].mean()
                        if not pd.isna(mean_value):
                            latency_data.append({
                                'workflow': workflow,
                                'metric': col.replace('metrics_', ''),
                                'value': mean_value
                            })
            
            if latency_data:
                latency_df_plot = pd.DataFrame(latency_data)
                # 创建分组柱状图
                workflow_latency_fig = px.bar(
                    latency_df_plot,
                    x='workflow',
                    y='value',
                    color='metric',
                    barmode='group',
                    title="工作流延迟对比",
                    labels={
                        'value': '平均延迟 (ms)',
                        'workflow': '工作流',
                        'metric': '延迟类型'
                    },
                    category_orders={"workflow": sorted(df['metadata_workflow'].unique())}
                )
            else:
                workflow_latency_fig = px.scatter(title="没有可用的延迟数据")
        else:
            workflow_latency_fig = px.scatter(title="没有可用的延迟指标")
    else:
        workflow_latency_fig = px.scatter(title="没有工作流数据")

    return (
        primary_fig, 
        throughput_fig, 
        latency_fig,
        columns,
        table_data,
        corr_fig,
        gpu_fig,
        scatter_fig,
        box_fig,
        timeline_fig,
        workflow_throughput_fig,
        workflow_latency_fig
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=True)

