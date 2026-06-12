"""测试 LLM 模块 — DeepSeek-V3 流式文本生成"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.llm import LLMError, ask_llm, ask_llm_stream


async def _fake_aiter_lines(lines):
    """真实的 async generator，模拟 httpx response.aiter_lines()"""
    for line in lines:
        yield line


def _mock_client(response):
    """构造 mock httpx.AsyncClient，返回指定 response"""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.stream.return_value.__aenter__ = AsyncMock(return_value=response)
    client.stream.return_value.__aexit__ = AsyncMock(return_value=None)
    return patch("server.llm.httpx.AsyncClient", return_value=client)


def _response_ok(lines):
    """构造 200 响应，aiter_lines 返回 lines"""
    resp = MagicMock()
    resp.status_code = 200
    resp.aiter_lines = lambda: _fake_aiter_lines(lines)
    return resp


class TestAskLLMStream:
    def test_yields_chunks(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"你好"}}]}\n',
            'data: {"choices":[{"delta":{"content":"世界"}}]}\n',
            "data: [DONE]\n",
        ]
        with _mock_client(_response_ok(lines)):
            result = asyncio.run(_collect_stream(ask_llm_stream("hello")))
            assert result == "你好世界"

    def test_stops_on_done(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"x"}}]}',
            "data: [DONE]",
            'data: {"choices":[{"delta":{"content":"y"}}]}',
        ]
        with _mock_client(_response_ok(lines)):
            result = asyncio.run(_collect_stream(ask_llm_stream("hello")))
            assert result == "x"

    def test_skips_empty_delta(self):
        lines = [
            'data: {"choices":[{"delta":{}}]}\n',
            'data: {"choices":[{"delta":{"content":"abc"}}]}\n',
            "data: [DONE]\n",
        ]
        with _mock_client(_response_ok(lines)):
            result = asyncio.run(_collect_stream(ask_llm_stream("hello")))
            assert result == "abc"

    def test_raises_on_http_error(self):
        resp = MagicMock()
        resp.status_code = 500
        resp.aread = AsyncMock(return_value=b"Internal Server Error")

        with _mock_client(resp):
            with pytest.raises(LLMError, match="500"):
                asyncio.run(_collect_stream(ask_llm_stream("hello")))


class TestAskLLM:
    def test_concatenates_chunks(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"你好"}}]}\n',
            'data: {"choices":[{"delta":{"content":"，世界"}}]}\n',
            "data: [DONE]\n",
        ]
        with _mock_client(_response_ok(lines)):
            result = asyncio.run(ask_llm("hello"))
            assert result == "你好，世界"


async def _collect_stream(agen):
    parts = []
    async for chunk in agen:
        parts.append(chunk)
    return "".join(parts)
