"""
工具4：获取 MySQL 表结构
"""

from langchain_core.tools import tool
from sqlalchemy import create_engine, inspect, text
from config import MYSQL_URL

## 全局缓存变量，用来缓存全库所有表的结构信息
_SCHEMA_CACHE = None


@tool
def get_schema_info(table_name: str = "") -> str:
    """
    获取 MySQL 数据库中指定表的结构信息（列名、类型、注释）。
    不传参数则列出所有表。

    参数:
        table_name: 表名（可选），如 "daily_sales"

    返回:
        表结构描述文本
    """
    global _SCHEMA_CACHE
    #判断缓存是否为空，只有首次执行才走数据库读取逻辑
    if _SCHEMA_CACHE is None:
        try:
            #建立数据库引擎
            engine = create_engine(MYSQL_URL)
            #创建数据库反射器，通过引擎自动读取数据库元信息（表、字段、约束、外键等）
            inspector = inspect(engine)
            #初始化全局缓存为空字典：key=表名，value=该表的结构文本列表
            _SCHEMA_CACHE = {}
            #循环遍历数据库里所有表名，t 是单张表名称
            for t in inspector.get_table_names():
                cols = []
                #读取当前表的所有字段
                for c in inspector.get_columns(t):
                    #获取注释，没有返回空字符串
                    comment = c.get("comment", "")
                    comment_str = f" -- {comment}" if comment else ""#
                    #拼接字段文本存入列表，格式：  字段名: 字段类型 -- 字段注释
                    cols.append(f"  {c['name']}: {c['type']}{comment_str}")
                #当前表所有字段循环完成，把字段列表存入全局缓存，key为表名
                _SCHEMA_CACHE[t] = cols
            # 检查外键
            for t in inspector.get_table_names():
                fks = inspector.get_foreign_keys(t)
                if fks:
                    _SCHEMA_CACHE[t].append("  --- 外键 ---")
                    for fk in fks:
                        # 拼接外键文本：本表关联字段 → 关联表.关联字段
                        _SCHEMA_CACHE[t].append(
                            f"  {fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}"
                        )
        except Exception as e:
            return f"[错误] 无法连接 MySQL: {str(e)}"

    if table_name:
        #判断用户传入了表名（table_name非空字符串），查询单表结构
        if table_name not in _SCHEMA_CACHE:
            #返回错误提示，和当前库所有表
            return f"[错误] 表 '{table_name}' 不存在。可用表: {', '.join(_SCHEMA_CACHE.keys())}"
        return f"表 {table_name}:\n" + "\n".join(_SCHEMA_CACHE[table_name])
    else:
        #table_name为空，用户未指定表，返回全部表结构
        result = []
        #name为表名，cols该表字段+外键文本列表
        for name, cols in _SCHEMA_CACHE.items():
            result.append(f"\n表 {name}:\n" + "\n".join(cols))
        return "\n".join(result)
