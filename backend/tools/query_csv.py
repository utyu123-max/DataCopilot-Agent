"""
工具2：DuckDB 查询 CSV

优化：
1. 全局 DuckDB 连接池 + CSV 表缓存，避免每次 IO
2. SQL 关键词白名单 + 黑名单双层校验，拦截 DROP/COPY/INSERT 等危险语句
3. 参数绑定防路径注入
4. 连接复用：多次调用共享同一连接
5. 自动重连：连接异常断开后自动重建
"""

import os
import re
import threading
import duckdb
from langchain_core.tools import tool
from config import CSV_SALES, CSV_CHANNELS, CSV_PRODUCTS



# 全局连接 + 缓存（惰性初始化 + 自动重连）
_conn = None #全局唯一内存连接
_conn_lock = threading.Lock() #互斥锁
_initialized = False #标记内存表是否加载完成
# DuckDB 连接错误类型（不同版本可能不同，兜底用 duckdb.Error）
_DISCONNECT_ERRORS = (duckdb.ConnectionException, duckdb.CatalogException, duckdb.IOException, duckdb.Error)


def _get_conn():
    """获取全局 DuckDB 连接（线程安全，惰性初始化，自动重连）"""
    global _conn, _initialized
    if _initialized and _conn is not None:
        # 快速探活：发一个无害查询，失败则触发重连
        try:
            _conn.execute("SELECT 1")
            return _conn
        except _DISCONNECT_ERRORS:
            _initialized = False

    with _conn_lock:
        if _initialized and _conn is not None:
            try:
                _conn.execute("SELECT 1")
                return _conn
            except _DISCONNECT_ERRORS:
                pass
        # 重建连接
        _conn = duckdb.connect(":memory:")
        _init_tables(_conn)
        _initialized = True
    return _conn


def _init_tables(con):
    """将 CSV 注册为 DuckDB 表（路径参数绑定，防注入）"""
    from pathlib import Path

    mappings = [
        ("sale_channels", CSV_CHANNELS),
        ("products", CSV_PRODUCTS),
        ("daily_sales", CSV_SALES),
    ]

    for table_name, csv_path in mappings:
        p = Path(csv_path)
        if not p.exists():
            raise FileNotFoundError(f"CSV 文件缺失: {csv_path}")
        abs_path = str(p.resolve())
        con.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto(?)",
            [abs_path]
        )


#sql安全检测（统一公共模块）
from tools.sql_safety import check_sql_safe



# Tool 定义
@tool
def query_csv(sql: str) -> str:
    """
    使用 DuckDB 对本地 CSV 文件执行 SQL 查询。
    可用的表:
        - daily_sales: 每日销售明细（约 2954 行）
        - sale_channels: 渠道维表（5 行）
        - products: 产品维表（8 行）

    参数:
        sql: DuckDB SQL 查询语句

    返回:
        查询结果（最多 200 行）的 markdown 格式表格
    """

    # ---- 安全检测 ----
    block_reason = check_sql_safe(sql, engine="duckdb")
    if block_reason:
        return block_reason

    # ---- 执行查询（自动重连由 _get_conn 内部处理） ----
    try:
        con = _get_conn()
        result = con.execute(sql)
        rows = result.fetchmany(200)
        columns = [desc[0] for desc in result.description]

        if not rows:
            return "[信息] 查询无匹配结果。"

        header = "| " + " | ".join(columns) + " |"
        sep = "|" + "|".join(["---" for _ in columns]) + "|"
        body = "\n".join(
            "| " + " | ".join(str(v) for v in row) + " |"
            for row in rows
        )
        return header + "\n" + sep + "\n" + body + f"\n\n(共返回 {len(rows)} 行)"
    except Exception as e:
        return f"[错误] DuckDB 查询失败: {str(e)}"
