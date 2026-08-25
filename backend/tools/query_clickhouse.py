"""
工具：ClickHouse 大数据查询（真实大数据接入）
安全校验复用公共模块 tools/sql_safety（白名单 + 黑名单，引擎定制词表）。

用于查询本地 Docker ClickHouse 中的真实大数据集（如天池淘宝用户行为 1 亿行）。
"""

from langchain_core.tools import tool
from config import CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DATABASE
from tools.sql_safety import check_sql_safe


# 连接缓存（懒初始化，复用连接避免重复握手）
_client = None


def _get_client():
    """惰性获取 ClickHouse 客户端（带自动重连）"""
    global _client
    from clickhouse_connect import get_client

    if _client is not None:
        try:
            _client.query("SELECT 1")  # 探活心跳
            return _client
        except Exception:
            _client = None  # 断连 → 重建

    _client = get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )
    return _client


@tool
def query_clickhouse(sql: str) -> str:
    """
    在 ClickHouse 上执行只读 SQL 查询（真实大数据分析）。
    用于查询大规模数据集（如 user_behavior 用户行为表，1 亿行真实数据），
    执行 GROUP BY / SUM / COUNT / 过滤等聚合分析。

    可用表:
    1. user_behavior（用户行为表，1 亿行），字段:
       - user_id: 用户ID (整数)
       - item_id: 商品ID (整数，注意不是 product_id)
       - category_id: 商品品类ID (整数)
       - behavior_type: 行为类型 (pv=点击 / cart=加购 / fav=收藏 / buy=购买)
       - ts: 行为时间戳 (Unix 秒)
    2. item_category（商品-品类维表，416 万商品），字段:
       - item_id: 商品ID
       - category_id: 商品品类ID
       用法: JOIN item_category ic ON b.item_id = ic.item_id 可查商品的品类
    3. item_names（商品-名称维表，8.2 万热门商品），字段:
       - item_id: 商品ID
       - item_name: 商品名称（如 "iPhone 15 Pro"、"戴森 V12 吸尘器"）
       覆盖范围: 只给购买数≥5 的热门商品起了真实风格名字；冷门商品没名字（JOIN 后会过滤掉）
       用法: LEFT JOIN item_names n ON b.item_id = n.item_id 可显示商品名称

    示例: 查询购买行为最多的热门商品（带名称和品类）:
    SELECT n.item_name, ic.category_id, COUNT(*) AS cnt
    FROM user_behavior b
    JOIN item_names n ON b.item_id = n.item_id
    JOIN item_category ic ON b.item_id = ic.item_id
    WHERE b.behavior_type = 'buy'
    GROUP BY n.item_name, ic.category_id
    ORDER BY cnt DESC LIMIT 5

    参数:
        sql: 只读 SELECT 语句（ClickHouse SQL 语法）

    返回:
        查询结果（最多 200 行，以 markdown 表格呈现）
    """
    #SQL 安全校验（白名单 + 黑名单）
    block_reason = check_sql_safe(sql, engine="clickhouse")
    if block_reason:
        return block_reason

    #执行查询
    try:
        client = _get_client()
        result = client.query(sql)
        columns = result.column_names
        rows = result.result_rows[:200]  # 最多 200 行，防止超大结果集

        if not rows:
            return "查询成功，但无匹配结果。"

        #组装 markdown 表格
        header = "| " + " | ".join(str(c) for c in columns) + " |"
        sep = "|" + "|".join(["---"] * len(columns)) + "|"
        body_lines = []
        for row in rows:
            body_lines.append("| " + " | ".join(str(v) for v in row) + " |")
        body = "\n".join(body_lines)

        total = len(result.result_rows)
        if total > 200:
            return f"{header}\n{sep}\n{body}\n\n(共 {total} 行，已展示前 200 行，可用 LIMIT/OFFSET 分页)"
        return f"{header}\n{sep}\n{body}"
    except Exception as e:
        return f"[错误] ClickHouse 查询失败: {str(e)}"
