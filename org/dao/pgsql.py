from __future__ import annotations

import os

from .engine import DbEngine, EngineConfig

from dotenv import load_dotenv

load_dotenv()  # 自动读取 .env 文件

DB_CONFIG = {
    'host': os.getenv('PGSQL_DB_HOST', '127.0.0.1'),
    'port': os.getenv('PGSQL_DB_PORT', '5432'),
    'database': os.getenv('PGSQL_DB_NAME', 'langflow'),
    'username': os.getenv('PGSQL_DB_USER', 'postgres'),
    'password': os.getenv('PGSQL_DB_PASSWORD', 'postgres')
}

pgsql_props = EngineConfig(
    **DB_CONFIG,
    name='pgsql'
)
pgsql_engine = DbEngine(pgsql_props)
