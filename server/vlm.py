"""Qwen-VL-Max 视觉推理 — 图片→文本"""

import asyncio
import logging
import time

import dashscope
from dashscope import MultiModalConversation

from server.config import DASHSCOPE_VLM_MODEL, VLM_TIMEOUT

logger = logging.getLogger(__name__)


class VLMError(Exception):
    """VLM 调用失败"""


async def image_to_text(image_base64: str, prompt: str = "请描述你看到的画面", trace: str = "-") -> str:
    """
    基于图片进行视觉推理，返回文本描述

    Args:
        image_base64: Base64 编码的 JPEG 图片 (不含 data: 前缀)
        prompt: 提示词

    Returns:
        VLM 生成的文本
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"image": f"data:image/jpeg;base64,{image_base64}"},
                {"text": prompt},
            ],
        }
    ]

    def _call():
        return MultiModalConversation.call(
            model=DASHSCOPE_VLM_MODEL,
            messages=messages,
        )

    start = time.monotonic()
    response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=VLM_TIMEOUT)
    elapsed = time.monotonic() - start

    if response.status_code != 200:
        raise VLMError(
            f"VLM returned {response.status_code}: {response.message}"
        )

    choices = response.output.choices
    if not choices:
        raise VLMError("VLM returned empty choices")

    content_list = choices[0].message.content
    if not content_list:
        raise VLMError("VLM returned empty content in first choice")
    text = content_list[0].get("text", "") or ""
    logger.info(
        "VLM done: trace=%s text=%r elapsed=%.2fs model=%s",
        trace, text[:100], elapsed, DASHSCOPE_VLM_MODEL,
    )
    return text
