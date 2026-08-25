"""
DataCopilot 模拟数据生成器
生成 3 张关联表：sale_channels(维度)、products(维度)、daily_sales(事实表)
支持单表查询、双表 JOIN、三表 JOIN 等多种 Agent 演示场景
"""

import csv
import random
import os
from datetime import datetime, timedelta

random.seed(42)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 表 1: 渠道维度表 (5 行)
# ============================================================
channels = [
    {"id": 1, "channel_name": "抖音",       "platform": "短视频", "cost_type": "CPA"},
    {"id": 2, "channel_name": "小红书",     "platform": "社媒",   "cost_type": "CPC"},
    {"id": 3, "channel_name": "百度SEM",    "platform": "搜索",   "cost_type": "CPC"},
    {"id": 4, "channel_name": "微信朋友圈", "platform": "社媒",   "cost_type": "CPM"},
    {"id": 5, "channel_name": "B站",        "platform": "视频",   "cost_type": "CPA"},
]

# ============================================================
# 表 2: 产品维度表 (8 行)
# ============================================================
products = [
    {"id": 1,  "product_name": "iPhone 15",           "category": "数码电子", "unit_price": 5999.00},
    {"id": 2,  "product_name": "AirPods Pro",          "category": "数码电子", "unit_price": 1499.00},
    {"id": 3,  "product_name": "戴森吸尘器",           "category": "家电",     "unit_price": 3299.00},
    {"id": 4,  "product_name": "美的电饭煲",           "category": "家电",     "unit_price": 699.00},
    {"id": 5,  "product_name": "南极人羽绒服",         "category": "服装",     "unit_price": 599.00},
    {"id": 6,  "product_name": "Nike运动鞋",           "category": "服装",     "unit_price": 899.00},
    {"id": 7,  "product_name": "三只松鼠坚果礼盒",     "category": "食品",     "unit_price": 168.00},
    {"id": 8,  "product_name": "良品铺子零食大礼包",   "category": "食品",     "unit_price": 149.00},
]

# ============================================================
# 表 3: 每日销售事实表 (~3000 行)
# 每渠道每天 1-2 个产品，365 天
# ============================================================
daily_sales = []
sale_id = 1
start_date = datetime(2026, 7, 29) - timedelta(days=364)  # 从今天往前推 365 天

for day_offset in range(365):
    sale_date = start_date + timedelta(days=day_offset)
    is_weekend = sale_date.weekday() >= 5
    month = sale_date.month

    for ch in channels:
        # 每个渠道每天卖 1-2 个产品
        product_count = random.choices([1, 2], weights=[0.4, 0.6])[0]
        picked_products = random.sample(products, product_count)

        for prod in picked_products:
            # 基础量（逐月递增趋势）
            base_mult = 1.0 + day_offset * 0.0008  # 全年增长约 30%
            # 周末流量高 30%
            weekend_mult = 1.3 if is_weekend else 1.0
            # 渠道特性
            channel_mult = {
                1: 1.5,   # 抖音流量大
                2: 1.2,
                3: 0.8,
                4: 1.1,
                5: 0.9,
            }[ch["id"]]
            # 季节性波动 (下半年: 6月618、11月双11、12月双12)
            season_mult = 1.0
            if month == 6:
                season_mult = 1.8
            elif month == 11:
                season_mult = 2.5
            elif month == 12:
                season_mult = 1.6
            elif month == 10:
                season_mult = 1.4

            impressions = int(random.randint(5000, 200000) * base_mult * channel_mult * season_mult)
            clicks = int(impressions * random.uniform(0.005, 0.08) * weekend_mult)
            cpc_value = random.uniform(0.3, 3.0) if ch["cost_type"] == "CPC" else 0
            cpm_value = random.uniform(5, 30) if ch["cost_type"] == "CPM" else 0
            cpa_unit = random.uniform(20, 150) if ch["cost_type"] == "CPA" else 0

            cost = 0
            if ch["cost_type"] == "CPC":
                cost = round(clicks * cpc_value, 2)
            elif ch["cost_type"] == "CPM":
                cost = round((impressions / 1000) * cpm_value, 2)
            elif ch["cost_type"] == "CPA":
                orders_est = int(clicks * random.uniform(0.01, 0.15))
                cost = round(orders_est * cpa_unit, 2)

            orders = int(clicks * random.uniform(0.01, 0.15))
            revenue = round(orders * prod["unit_price"], 2)

            daily_sales.append({
                "id": sale_id,
                "sale_date": sale_date.strftime("%Y-%m-%d"),
                "channel_id": ch["id"],
                "product_id": prod["id"],
                "impressions": impressions,
                "clicks": clicks,
                "cost": cost,
                "orders": orders,
                "revenue": revenue,
            })
            sale_id += 1


# ============================================================
# 写入 CSV
# ============================================================
def write_csv(file_name, rows, fieldnames):
    path = os.path.join(OUTPUT_DIR, file_name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"[CSV] {file_name}: {len(rows)} 行 → {path}")


write_csv("sale_channels.csv", channels, ["id", "channel_name", "platform", "cost_type"])
write_csv("products.csv", products, ["id", "product_name", "category", "unit_price"])
write_csv("daily_sales.csv", daily_sales,
          ["id", "sale_date", "channel_id", "product_id", "impressions", "clicks", "cost", "orders", "revenue"])

# ============================================================
# 写入 MySQL seed.sql
# ============================================================
sql_path = os.path.join(OUTPUT_DIR, "seed.sql")

def sql_escape(v):
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return f"'{v}'"
    return str(v)

with open(sql_path, "w", encoding="utf-8") as f:
    f.write("-- DataCopilot 数据库初始化脚本\n")
    f.write("-- 创建数据库\n\n")
    f.write("CREATE DATABASE IF NOT EXISTS datacopilot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n")
    f.write("USE datacopilot;\n\n")

    # sale_channels
    f.write("-- 渠道维度表\n")
    f.write("DROP TABLE IF EXISTS daily_sales;\n")
    f.write("DROP TABLE IF EXISTS sale_channels;\n")
    f.write("DROP TABLE IF EXISTS products;\n\n")

    f.write("""CREATE TABLE sale_channels (
    id INT PRIMARY KEY,
    channel_name VARCHAR(50) NOT NULL COMMENT '渠道名称',
    platform VARCHAR(20) NOT NULL COMMENT '平台类型',
    cost_type VARCHAR(10) NOT NULL COMMENT '计费方式: CPA/CPC/CPM'
) COMMENT '渠道维度表';\n\n""")

    cols = ["id", "channel_name", "platform", "cost_type"]
    for row in channels:
        vals = ", ".join(sql_escape(row[c]) for c in cols)
        f.write(f"INSERT INTO sale_channels ({', '.join(cols)}) VALUES ({vals});\n")

    # products
    f.write("\n-- 产品维度表\n")
    f.write("""CREATE TABLE products (
    id INT PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL COMMENT '产品名称',
    category VARCHAR(20) NOT NULL COMMENT '产品类别',
    unit_price DECIMAL(10,2) NOT NULL COMMENT '单价'
) COMMENT '产品维度表';\n\n""")

    cols = ["id", "product_name", "category", "unit_price"]
    for row in products:
        vals = ", ".join(sql_escape(row[c]) for c in cols)
        f.write(f"INSERT INTO products ({', '.join(cols)}) VALUES ({vals});\n")

    # daily_sales
    f.write("\n-- 每日销售事实表 (核心大表)\n")
    f.write("""CREATE TABLE daily_sales (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sale_date DATE NOT NULL COMMENT '销售日期',
    channel_id INT NOT NULL COMMENT '渠道ID',
    product_id INT NOT NULL COMMENT '产品ID',
    impressions INT DEFAULT 0 COMMENT '曝光量',
    clicks INT DEFAULT 0 COMMENT '点击量',
    cost DECIMAL(10,2) DEFAULT 0 COMMENT '花费',
    orders INT DEFAULT 0 COMMENT '订单数',
    revenue DECIMAL(12,2) DEFAULT 0 COMMENT '收入',
    FOREIGN KEY (channel_id) REFERENCES sale_channels(id),
    FOREIGN KEY (product_id) REFERENCES products(id),
    INDEX idx_date (sale_date),
    INDEX idx_channel (channel_id),
    INDEX idx_product (product_id)
) COMMENT '每日销售事实表';\n\n""")

    cols = ["id", "sale_date", "channel_id", "product_id", "impressions", "clicks", "cost", "orders", "revenue"]
    for i, row in enumerate(daily_sales):
        vals = ", ".join(sql_escape(row[c]) for c in cols)
        suffix = ";" if i == len(daily_sales) - 1 else ";"
        f.write(f"INSERT INTO daily_sales ({', '.join(cols)}) VALUES ({vals}){suffix}\n")

    f.write("\n-- 数据导入完成\n")

total_sales = len(daily_sales)
print(f"[SQL] seed.sql: channels={len(channels)} products={len(products)} sales={total_sales} → {sql_path}")
print("\n数据生成完毕！摘要：")
print(f"  渠道维表: {len(channels)} 行")
print(f"  产品维表: {len(products)} 行")
print(f"  销售事实表: {total_sales} 行 (365天 x 5渠道 x 1-2产品)")
print(f"\n典型查询示例 -- 单表: SELECT * FROM daily_sales WHERE sale_date = '2025-11-11'")
print(f"典型查询示例 -- 双表JOIN: SELECT c.channel_name, SUM(s.revenue) FROM daily_sales s JOIN sale_channels c ON s.channel_id=c.id GROUP BY c.channel_name")
print(f"典型查询示例 -- 三表JOIN: SELECT c.channel_name, p.category, SUM(s.cost), SUM(s.revenue), SUM(s.revenue-s.cost) FROM daily_sales s JOIN sale_channels c ON s.channel_id=c.id JOIN products p ON s.product_id=p.id GROUP BY c.channel_name, p.category")
