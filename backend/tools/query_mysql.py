"""
工具1：MySQL 只读查询
安全校验复用公共模块 tools/sql_safety（统一白名单 + 黑名单）。
"""


from langchain_core.tools import tool
from sqlalchemy import create_engine, text
from config import MYSQL_URL
from tools.sql_safety import check_sql_safe


@tool
def query_mysql(sql: str) -> str:
    """
    在连接的 MySQL 数据库上执行只读 SQL 查询。
    用于查询 sales_channels、products、daily_sales 等表。

    参数:
        sql: 只读 SELECT 语句

    返回:
        查询结果（最多 200 行，以 markdown 表格呈现）
    """
    block_reason = check_sql_safe(sql, engine="mysql")
    if block_reason:
        return block_reason

    try:
        engine = create_engine(MYSQL_URL)
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            # fetchmany(N)：最多读取200条记录，避免超大结果集卡死
            rows = result.fetchmany(200)
            #获取字段名
            columns = list(result.keys())

            if not rows:
                return "[信息] 查询无匹配结果。"

            # 格式化为 markdown 表格
            header = "| " + " | ".join(columns) + " |"
            sep = "|" + "|".join(["---" for _ in columns]) + "|"
            body = "\n".join(
                "| " + " | ".join(str(v) for v in row) + " |"
                for row in rows
            )
            return header + "\n" + sep + "\n" + body + f"\n\n(共返回 {len(rows)} 行)"
    except Exception as e:
        return f"[错误] SQL 执行失败: {str(e)}"
