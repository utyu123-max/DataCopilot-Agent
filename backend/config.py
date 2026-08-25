"""
DataCopilot 配置管理
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ============================================================
# LLM 配置（百炼 Qwen）
# ============================================================
QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
QWEN_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-max")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))

# 摘要模型（便宜型号，用于上下文压缩，降低长对话成本）
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "qwen-turbo")
# 上下文压缩触发阈值：消息超过该条数就滚动摘要
CONTEXT_MAX_MESSAGES = int(os.getenv("CONTEXT_MAX_MESSAGES", "8"))

# ============================================================
# MySQL 配置
# ============================================================
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "datacopilot")
MYSQL_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# ============================================================
# CSV / DuckDB 配置
# ============================================================
CSV_DIR = BASE_DIR / "data"
CSV_SALES = CSV_DIR / "daily_sales.csv"
CSV_CHANNELS = CSV_DIR / "sale_channels.csv"
CSV_PRODUCTS = CSV_DIR / "products.csv"

# ============================================================
# ClickHouse 配置（真实大数据接入，本地 Docker）
# ============================================================
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "datacopilot")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")

# ============================================================
# 沙箱配置
# ============================================================
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "15"))   # 代码执行超时（秒）
SANDBOX_MAX_MEMORY_MB = int(os.getenv("SANDBOX_MAX_MEMORY_MB", "256"))#最大内存上限256M
