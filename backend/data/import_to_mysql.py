"""
一次性数据导入脚本：用 Pandas + SQLAlchemy 把 CSV 导进 MySQL
"""

import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = "mysql+pymysql://root:123456@localhost:3306/datacopilot?charset=utf8mb4"

engine = create_engine(DB_URL)

# 先关掉外键检查，按正确顺序清表 + 灌数据
with engine.begin() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    conn.execute(text("TRUNCATE TABLE daily_sales"))
    conn.execute(text("TRUNCATE TABLE sale_channels"))
    conn.execute(text("TRUNCATE TABLE products"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

for table_name, csv_path in [
    ("sale_channels", "D:/aiCoding/project2/backend/data/sale_channels.csv"),
    ("products", "D:/aiCoding/project2/backend/data/products.csv"),
    ("daily_sales", "D:/aiCoding/project2/backend/data/daily_sales.csv"),
]:
    df = pd.read_csv(csv_path)
    df.to_sql(table_name, engine, if_exists="append", index=False)
    print(f"[OK] {table_name}: {len(df)} 行")

# 验证
with engine.connect() as conn:
    result = conn.execute(text("SELECT MIN(sale_date), MAX(sale_date), COUNT(*) FROM daily_sales"))
    row = result.fetchone()
    print(f"\nMySQL 导入结果: 最早 {row[0]}, 最晚 {row[1]}, 共 {row[2]} 行")
