"""
工具3：沙箱中执行 Python 代码（升级版：沙箱内可查询 DuckDB 数据）
"""

import subprocess
import tempfile
import sys
import json as _json
from langchain_core.tools import tool
from config import SANDBOX_TIMEOUT, CSV_SALES, CSV_CHANNELS, CSV_PRODUCTS


@tool
def execute_python(code: str) -> str:
    """
    在隔离沙箱中执行 Python 代码。
    用于 SQL 无法完成的复杂计算（时间序列、聚类、异常检测、自定义评分）。

    沙箱内提供 query(sql) 函数:
        执行只读 SELECT，返回 [{"列名": 值}, ...] 列表。
        示例: rows = query("SELECT channel_name, SUM(revenue) AS total FROM daily_sales GROUP BY channel_name")

    可用模块: json, math, statistics, datetime, collections
    禁止: import（任何模块）、文件系统(open)、网络、exec/eval

    沙箱限制:
        - 不能 import 模块
        - 不能访问文件系统 / 网络
        - query 只允许 SELECT/WITH 等只读语句
        - 执行超时: 15 秒

    参数:
        code: 要执行的 Python 代码字符串

    返回:
        标准输出 (stdout) 内容
    """
    # 注入 CSV 路径（json.dumps 转义，防路径注入）
    paths = {
        "sale_channels": str(CSV_CHANNELS),
        "products": str(CSV_PRODUCTS),
        "daily_sales": str(CSV_SALES),
    }
    paths_json = _json.dumps(paths, ensure_ascii=False)

    preamble = """import json, math, statistics
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import datetime as _datetime_mod
import collections as _collections_mod
import builtins, uuid
del uuid

_CSV_PATHS = __PATHS__

def _build_query():
    import duckdb, re
    con = [None]
    def query(sql):
        sql = str(sql)
        if not re.match(r"^\\s*(SELECT|WITH|EXPLAIN|DESCRIBE|SHOW)\\b", sql, re.IGNORECASE):
            return "[安全拦截] 只允许 SELECT/WITH/EXPLAIN/DESCRIBE/SHOW 查询语句。"
        m = re.search(r"\\b(DROP|TRUNCATE|DELETE|INSERT|UPDATE|ALTER|CREATE\\s+OR\\s+REPLACE|COPY|ATTACH|DETACH|INSTALL|LOAD|EXPORT|IMPORT|EXECUTE)\\b", sql, re.IGNORECASE)
        if m:
            return "[安全拦截] 禁止使用 '%s' 操作。" % m.group(1)
        if con[0] is None:
            con[0] = duckdb.connect(":memory:")
            for tname, path in _CSV_PATHS.items():
                con[0].execute("CREATE OR REPLACE TABLE %s AS SELECT * FROM read_csv_auto(?)" % tname, [path])
        cur = con[0].execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(200)
        return [dict(zip(cols, row)) for row in rows]
    return query

query = _build_query()
del _build_query

_SAFE_MODULES = {"json": json, "math": math, "statistics": statistics, "datetime": _datetime_mod, "collections": _collections_mod}
def _no_import(name, *a, **k):
    return _SAFE_MODULES.get(name.split(".")[0])
builtins.__import__ = _no_import
builtins.open = None
builtins.exec = None
builtins.eval = None
"""

    full_code = preamble.replace("__PATHS__", paths_json) + "\n" + code

    try:
        result = subprocess.run(
            # 调用当前运行的 Python 解释器，新开独立子进程
            [sys.executable, "-c", full_code],
            capture_output=True,  # 捕获stdout、stderr
            text=True,            # 输出转为字符串，不是bytes
            timeout=SANDBOX_TIMEOUT,  # 超时杀死进程，防止死循环
            cwd=tempfile.gettempdir(),  # 工作目录设系统临时目录
        )

        stdout = result.stdout.strip()  # 沙箱输出
        stderr = result.stderr.strip()  # 沙箱错误

        if stderr:
            return f"[沙箱错误]\n{stderr[:1000]}"

        if not stdout:
            return "[沙箱] 代码执行完毕，无输出。"

        return stdout[:5000]  # 截断过长输出
    except subprocess.TimeoutExpired:
        return f"[错误] 代码执行超时（>{SANDBOX_TIMEOUT}秒），请简化代码。"
    except Exception as e:
        return f"[错误] 沙箱执行失败: {str(e)}"
