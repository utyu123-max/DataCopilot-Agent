"""
SQL 安全校验公共模块（统一的白名单 + 黑名单）
所有查询工具（MySQL / DuckDB / ClickHouse）共用同一套校验，
词表按引擎定制（不同引擎有不同的危险语句），策略统一管理。
"""

import re

# 白名单：只允许这些只读语句开头（默认拒绝）
_ALLOWED_START = re.compile(
    r"^\s*(SELECT|WITH|EXPLAIN|DESCRIBE|SHOW)\b",
    re.IGNORECASE,
)

# 基础黑名单：所有引擎通用的危险操作
_BASE_BLOCKED = [
    "DROP", "TRUNCATE", "DELETE", "INSERT", "UPDATE", "ALTER",
    "CREATE", "GRANT", "REVOKE", "RENAME", "REPLACE",
]

# 引擎特有黑名单：不同引擎独有的危险语句
_ENGINE_BLOCKED = {
    # DuckDB：文件读写、挂载数据库、装扩展
    "duckdb": ["COPY", "ATTACH", "DETACH", "INSTALL", "LOAD", "EXPORT", "IMPORT"],
    # ClickHouse：集群控制、系统级操作、优化语句
    "clickhouse": ["KILL", "SYSTEM", "SET", "OPTIMIZE", "EXECUTE", "EXPORT", "IMPORT"],
    # MySQL：事务/锁相关
    "mysql": ["LOCK", "UNLOCK", "HANDLER", "LOAD"],
}


def _compile_blocked(engine: str) -> re.Pattern:
    words = list(_BASE_BLOCKED)
    words.extend(_ENGINE_BLOCKED.get(engine, []))
    return re.compile(r"\b(" + "|".join(words) + r")\b", re.IGNORECASE)


_BLOCKED_CACHE: dict[str, re.Pattern] = {}


def check_sql_safe(sql: str, engine: str = "generic") -> str | None:
    """
    检查 SQL 是否安全。
    返回 None = 安全；返回 str = 拒绝理由。
    """
    stripped = sql.strip()

    #白名单：管开头意图（默认拒绝，只放行只读语句）
    if not _ALLOWED_START.match(stripped):
        return "[安全拦截] 只允许 SELECT/WITH/EXPLAIN/DESCRIBE/SHOW 查询语句。"

    #黑名单：管全文隐藏的坏词（按引擎定制）
    if engine not in _BLOCKED_CACHE:
        _BLOCKED_CACHE[engine] = _compile_blocked(engine)
    match = _BLOCKED_CACHE[engine].search(stripped)
    if match:
        return f"[安全拦截] 禁止使用 '{match.group(1)}' 操作。"

    return None
