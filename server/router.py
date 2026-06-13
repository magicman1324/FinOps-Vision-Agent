"""双层意图路由 — L0 关键词正则 + L1 LLM 二分类兜底"""

import re
import logging

logger = logging.getLogger(__name__)

# L0: 视觉意图关键词模式 — 命中任一即返回 visual
VISUAL_PATTERNS = [
    # 对象辨识
    r"这是什么", r"那是什么", r"什么东西", r"是谁",
    # 视觉属性
    r"什么颜色", r"啥颜色", r"什么形状", r"长什么样",
    r"多大[的]?尺寸", r"多大[的]?个头",
    # 空间方位
    r"在哪[儿里]?",
    # 数量统计（视觉场景内）
    r"有几个", r"多少个", r"多少[个只件张把台辆朵棵粒座]",
    # 视觉感知动词
    r"看到", r"看见", r"见到", r"注意到",
    # 画面/媒体指代
    r"画面", r"图片", r"照片", r"图像", r"屏幕",
    r"摄像头", r"镜头", r"视频",
    # 指代 + 物品
    r"这个(东西|物品|物件|颜色|形状|人|是啥|是什么)",
    r"那个(东西|物品|物件|颜色|形状|人|是啥|是什么)",
    # 第一人称空间锚点
    r"手里", r"手上", r"面前", r"眼前",
    r"桌子上", r"地上", r"墙上",
    # 展示请求
    r"展示", r"显示给我",
    # 外观描述
    r"[长是]什么样[子]?", r"外观",
]

L1_SYSTEM_PROMPT = (
    "你是一个意图分类器。判断用户的问题是否需要借助视觉（看到画面/图片/摄像头）才能回答。"
    "只需要回复 'visual' 或 'textual'，不要解释，不要标点，不要其他内容。"
)


def classify_intent_l0(text: str) -> str:
    """L0 关键词路由：正则匹配，零延迟零成本"""
    if not text or not text.strip():
        return "textual"

    for pattern in VISUAL_PATTERNS:
        if re.search(pattern, text):
            logger.debug("L0 visual match: pattern=%r text=%r", pattern, text[:80])
            return "visual"

    return "textual"


async def classify_intent_l1(text: str) -> str:
    """L1 LLM 二分类：当 L0 未命中时，用 DeepSeek-V3 兜底"""
    from server.llm import ask_llm

    raw = await ask_llm(text, system_prompt=L1_SYSTEM_PROMPT)
    cleaned = raw.strip().lower()

    if "visual" in cleaned:
        logger.info("L1 → visual: text=%r", text[:80])
        return "visual"

    logger.debug("L1 → textual: text=%r", text[:80])
    return "textual"


