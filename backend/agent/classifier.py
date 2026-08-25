"""
意图分类器：判断用户输入是"数据分析请求"还是"闲聊/领域外"。

"""

from openai import OpenAI
from config import QWEN_API_KEY, QWEN_BASE_URL, SUMMARY_MODEL

_client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)

CLASSIFY_PROMPT = """判断用户输入是否为"数据分析请求"。

数据分析请求包括：查询/比较/统计销售数据、渠道/商品/时间维度分析、生成图表、
ROI/订单/花费/曝光等业务指标问题、对数据的追问和修正。

非数据分析请求包括：闲聊问候、创作类（写诗/写文章/写代码）、生活类（天气/美食/娱乐）、
与数据分析无关的身份或能力问题。

只回答一个词：business 或 casual
输入：{user_input}"""


def classify_intent(text: str) -> str:
    """返回 'business' 或 'casual'。任何异常默认返回 'business'（放行）。"""
    try:
        resp = _client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFY_PROMPT.format(user_input=text[:300])},
            ],
            temperature=0,
            max_tokens=5,
        )
        answer = (resp.choices[0].message.content or "").strip().lower()
        return "business" if "business" in answer else "casual"
    except Exception as e:
        print(f"[Classifier] 分类失败，默认放行: {e}")
        return "business"
