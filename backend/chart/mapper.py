"""
图表意图 → 完整 ECharts Option 映射器
LLM 只需生成简化的图表意图 JSON，
由本模块映射为完整的 ECharts Option 配置。
"""

import json
import re


def _to_hex(color):
    """把任意颜色字符串转成 #xxxxxx，无法识别返回 None"""
    #如果不是字符串
    if not isinstance(color, str):
        return None
    c = color.strip().lower()
    if not c:
        return None
    if c.startswith("#"):
        if len(c) == 4:
            return "#" + c[1] * 2 + c[2] * 2 + c[3] * 2
        if len(c) == 7:
            return c
        return None
    return _COLOR_NAMES.get(c)


_COLOR_NAMES = {
    # CSS 标准色
    "red": "#ef4444", "green": "#22c55e", "blue": "#3b82f6",
    "yellow": "#eab308", "orange": "#f97316", "purple": "#a855f7",
    "pink": "#ec4899", "cyan": "#06b6d4", "teal": "#14b8a6",
    "black": "#1f2937", "white": "#f9fafb", "gray": "#9ca3af",
    # 中文别名
    "红": "#ef4444", "红色": "#ef4444",
    "绿": "#22c55e", "绿色": "#22c55e",
    "蓝": "#3b82f6", "蓝色": "#3b82f6",
    "黄": "#eab308", "黄色": "#eab308",
    "紫": "#a855f7", "紫色": "#a855f7",
    "粉": "#ec4899", "粉色": "#ec4899",
    "橙": "#f97316", "橙色": "#f97316",
    "黑": "#1f2937", "黑色": "#1f2937",
    "白": "#f9fafb", "白色": "#f9fafb",
    "灰": "#9ca3af", "灰色": "#9ca3af",
}

#映射图表意图
def map_chart_intent(intent: dict) -> dict:
    chart_type = intent.get("type", "bar")
    title = intent.get("title", "")
    data = intent.get("data", [])

    # 主题色板（支持自定义颜色）
    user_color = (intent.get("options") or {}).get("color", None)
    #初始化色板变量。
    color_palette = None
    if user_color:
        if isinstance(user_color, list):
            #复制作为全局色板
            color_palette = list(user_color)
        else:
            hex_color = _to_hex(user_color)
            if hex_color:
                base = hex_color.lstrip('#')
                #十六进制字符串拆分，转十进制 RGB 数值。
                r, g, b = int(base[0:2], 16), int(base[2:4], 16), int(base[4:6], 16)
                #基于基础色，自动生成 5 种变体：提亮、原色、变暗、偏绿、偏红；
                color_palette = [
                    f"#{min(255,r+40):02x}{min(255,g+40):02x}{min(255,b+40):02x}",
                    hex_color,
                    f"#{max(0,r-40):02x}{max(0,g-40):02x}{max(0,b-40):02x}",
                    f"#{min(255,r):02x}{min(255,g+60):02x}{min(255,b):02x}",
                    f"#{max(0,r-60):02x}{min(255,g):02x}{max(0,b-60):02x}",
                ]

    if not color_palette:
        #使用Echarts官方色组
        color_palette = [
            "#5470c6", "#91cc75", "#fac858", "#ee6666",
            "#73c0de", "#3ba272", "#fc8452", "#9a60b4",
            "#ea7ccc", "#48b3c3"
        ]
    #定义所有图表通用基础配置
    base_option = {
        "color": color_palette,
        "title": {
            "text": title,
            "left": "center",
            "textStyle": {"fontSize": 14, "fontWeight": "normal"}
        },
        #悬浮提示区分：柱状/折现axis坐标轴触发，饼图扇区触发
        "tooltip": {"trigger": "axis" if chart_type != "pie" else "item"},
        #图例：底部横向滚动图例，图例过多自动分页；适配暗色主题浅色文字。
        "legend": {
            "type": "scroll",
            "orient": "horizontal",
            "bottom": 0,
            "left": "center",
            "textStyle": {"fontSize": 11, "color": "#bbb"},
            "pageIconColor": "#aaa",
            "pageTextStyle": {"color": "#aaa"},
            "itemWidth": 10,
            "itemHeight": 10,
            "itemGap": 8,
        },
        #绘图区域边距，bottom 预留高度放图例；containLabel 坐标轴文字不超出网格范围。
        "grid": {"left": "3%", "right": "4%", "bottom": "18%", "containLabel": True},
    }

    if chart_type == "pie":
        #数值
        y_field = intent.get("y", "value")
        #分类名称
        x_field = intent.get("x", "name")
        max_val = max((float(d.get(y_field, 0) or 0) for d in data), default=0)
        if max_val >= 10000:
            decimals = 0
        elif max_val >= 1:
            decimals = 2
        else:
            decimals = 4

        pie_data = [{"name": str(d.get(x_field, ""))[:14],
                     "value": round(float(d.get(y_field, 0) or 0),decimals)}
                    for d in data]

        return {
            **{k: v for k, v in base_option.items() if k != "grid"},
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}<br/>{c} ({d}%)"
            },
            "series": [{
                "type": "pie",
                "radius": ["36%", "60%"],
                "center": ["50%", "44%"],
                "avoidLabelOverlap": True,
                "data": pie_data,
                "label": {
                    "formatter": "{b}",
                    "color": "#e5e7eb",
                    "fontSize": 11,
                },
                "labelLine": {
                    "length": 8,
                    "length2": 8,
                    "lineStyle": {"width": 1}
                },
                "labelLayout": {"hideOverlap": True},
                "emphasis": {
                    "label": {"fontSize": 13, "fontWeight": "bold"},
                    "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.3)"}
                }
            }]
        }

    # bar / line / scatter
    ## 从绘图意图读取分类字段和数值
    x_field = intent.get("x", "name")
    y_field = intent.get("y", "value")
    #提取所有的分类标签和对应数值
    x_data = [str(d.get(x_field, "")) for d in data]
    y_data = [d.get(y_field, 0) for d in data]

    # 单色应用：把所有柱子用同一颜色
    series_color = color_palette[0] if user_color and not isinstance(user_color, list) else None

    series = {
        "type": chart_type,
        "data": y_data,
        "smooth": True if chart_type == "line" else False,
        "itemStyle": {
            "borderRadius": [4, 4, 0, 0] if chart_type == "bar" else 0,
            **({"color": series_color} if series_color else {})
        },
    }

    base_option["xAxis"] = {
        "type": "category",
        "data": x_data,
        "axisLabel": {
            "interval": 0,
            "rotate": 30 if len(x_data) > 4 else 0,
            "fontSize": 11,
            "color": "#cbd5e1",
        },
        "axisTick": {"alignWithLabel": True}
    }
    base_option["yAxis"] = {
        "type": "value",
        "axisLabel": {"color": "#9ca3af", "fontSize": 11},
        "splitLine": {"lineStyle": {"color": "#374151"}}
    }
    base_option["series"] = [series]

    return base_option


def parse_chart_from_code_output(output: str) -> dict | None:
    """从 LLM 回复中提取图表意图 JSON。支持 [CHART] / ```json``` / 独立 JSON 三种格式"""
    raw = None

    # [CHART]...[/CHART]
    match = re.search(r"\[CHART\]\s*(.*?)\s*\[/CHART\]", output, re.DOTALL)
    if match:
        try:
            raw = json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # ```json ... ```
    if not raw:
        match = re.search(r"```json\s*(.*?)\s*```", output, re.DOTALL)
        if match:
            try:
                raw = json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

    # 文本内独立裸 JSON
    if not raw:
        start = output.find("{")
        if start >= 0:
            depth = 0
            for i in range(start, len(output)):
                if output[i] == "{":
                    depth += 1
                elif output[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            #代表找到成对闭合的最外层 JSON
                            raw = json.loads(output[start:i+1])
                            if "type" in raw:
                                break
                        except json.JSONDecodeError:
                            pass

    if not raw or "type" not in raw:
        return None

    data = raw.get("data") or []
    x = raw.get("x")
    y = raw.get("y")

    if data and (not x or x not in (data[0].keys() if data else ())):
        if data:
            keys = list(data[0].keys())
            for k in keys:
                if k in raw:
                    continue
                if "字段" in str(k) or k in ("x", "y"):
                    continue
                if not x:
                    x = k
                elif not y:
                    y = k
            if not x or not y:
                leftover = [k for k in keys if k not in ("type", "title", "x", "y", "data") and "字段" not in str(k)]
                if not x and len(leftover) >= 1:
                    x = leftover[0]
                if not y and len(leftover) >= 2:
                    y = leftover[1]

    if data and isinstance(data, list) and data:
        first = data[0]
        if "x字段" in first:
            new_data = []
            for d in data:
                new_d = {}
                for k, v in d.items():
                    if k == "x字段":
                        new_d[x or "name"] = v
                    elif k == "y字段":
                        new_d[y or "value"] = v
                    else:
                        new_d[k] = v
                new_data.append(new_d)
            data = new_data

    return {
        "type": raw.get("type"),
        "title": raw.get("title", ""),
        "x": x,
        "y": y,
        "data": data,
        "options": raw.get("options", {}),
    }
