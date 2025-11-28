from __future__ import annotations

import os
from dotenv import load_dotenv
load_dotenv()  # 自动读取 .env 文件

from .engine import DbEngine, EngineConfig


DB_CONFIG = {
    'host': os.getenv('DORIS_DB_HOST', '127.11.16.23'),
    'port': os.getenv('DORIS_DB_PORT', '9030'),
    'database': os.getenv('DORIS_DB_NAME', 'test_db'),
    'username': os.getenv('DORIS_DB_USER', 'root'),
    'password': os.getenv('DORIS_DB_PASSWORD', '')
}

doris_props = EngineConfig(
    **DB_CONFIG,
    name='doris'
)

doris_engine = DbEngine(doris_props)

