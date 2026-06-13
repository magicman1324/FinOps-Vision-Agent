"""DeepSeek-V3 纯文本推理 — 流式文本生成"""

import json
import logging
import time

import httpx

from server.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, LLM_TIMEOUT

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 调用失败"""


async def ask_llm_stream(prompt: str, system_prompt: str = None):
    """流式调用 DeepSeek-V3，逐 chunk yield 文本"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": True,
    }

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT, trust_env=False) as client:
        async with client.stream(
            "POST",
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise LLMError(f"DeepSeek returned {response.status_code}: {body}")

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    elapsed = time.monotonic() - start
    logger.info("LLM done: elapsed=%.2fs, model=%s", elapsed, DEEPSEEK_MODEL)


async def ask_llm(prompt: str, system_prompt: str = None) -> str:
    """非流式汇总，返回完整文本"""
    parts = []
    async for chunk in ask_llm_stream(prompt, system_prompt):
        parts.append(chunk)
    return "".join(parts)
