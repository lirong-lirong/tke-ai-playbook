import os

class Config:
    # 直接从环境变量获取值
    REPORTS_DIR = os.getenv('REPORTS_DIR', '/app/reports')
    API_KEY = os.getenv('API_KEY', 'your-secret-api-key')
    DATA_REFRESH_INTERVAL = int(os.getenv('DATA_REFRESH_INTERVAL', 60))