from __future__ import annotations

import os


from .engine import DbEngine, EngineConfig
from dotenv import load_dotenv
load_dotenv()  # 自动读取 .env 文件

DB_CONFIG = {
    'host': os.getenv('MYSQL_DB_HOST', '127.0.0.1'),
    'port': os.getenv('MYSQL_DB_PORT', '3306'),
    'database': os.getenv('MYSQL_DB_NAME', 'test_db'),
    'username': os.getenv('MYSQL_DB_USER', 'root'),
    'password': os.getenv('MYSQL_DB_PASSWORD', '')
}

mysql_props = EngineConfig(
    **DB_CONFIG,
    name='mysql'
)
mysql_engine = DbEngine(mysql_props)
