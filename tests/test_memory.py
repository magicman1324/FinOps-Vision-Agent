"""测试三层语义压缩记忆"""

import asyncio
from unittest.mock import AsyncMock, patch

from server.memory import ConversationMemory


class TestShortMemory:
    """短窗口 — 最近 N 轮完整保存"""

    def test_stores_and_retrieves_turns(self):
        mem = ConversationMemory(max_short_turns=3)
        mem.add_turn("你好", "你好！有什么可以帮你的？")
        mem.add_turn("今天天气怎么样", "今天是晴天")

        history = mem.get_short_history()
        assert len(history) == 4
        assert history[0] == {"role": "user", "content": "你好"}
        assert history[3] == {"role": "assistant", "content": "今天是晴天"}

    def test_evicts_beyond_max_short(self):
        mem = ConversationMemory(max_short_turns=2)
        mem.add_turn("第1轮", "回复1")
        mem.add_turn("第2轮", "回复2")
        mem.add_turn("第3轮", "回复3")

        history = mem.get_short_history()
        assert len(history) == 4
        assert history[0]["content"] == "第2轮"
        assert history[3]["content"] == "回复3"

    def test_evicted_goes_to_mid(self):
        mem = ConversationMemory(max_short_turns=2)
        mem.add_turn("第1轮", "回复1")
        mem.add_turn("第2轮", "回复2")
        mem.add_turn("第3轮", "回复3")

        assert mem.mid_count == 1
        assert "第1轮" in mem._mid[0]
        assert "回复1" in mem._mid[0]

    def test_turn_count_increments(self):
        mem = ConversationMemory()
        mem.add_turn("a", "b")
        mem.add_turn("c", "d")
        assert mem.turn_count == 2
        assert mem.short_turns == 2

    def test_mid_not_compressed_initially(self):
        mem = ConversationMemory(max_short_turns=1)
        mem.add_turn("第1轮", "回复1")
        mem.add_turn("第2轮", "回复2")
        assert mem.mid_count == 1
        assert not mem.mid_compressed


class TestContextGeneration:
    """get_context() 组装三层上下文"""

    def test_empty_context(self):
        mem = ConversationMemory()
        assert mem.get_context() == ""

    def test_short_only_context(self):
        mem = ConversationMemory(max_short_turns=3)
        mem.add_turn("你好", "你好！")
        ctx = mem.get_context()
        assert "用户: 你好" in ctx
        assert "AI: 你好！" in ctx

    def test_context_with_mid(self):
        mem = ConversationMemory(max_short_turns=2)
        mem.add_turn("第1轮", "回复1")
        mem.add_turn("第2轮", "回复2")
        mem.add_turn("第3轮", "回复3")

        ctx = mem.get_context()
        assert "[之前]" in ctx
        assert "第1轮" in ctx

    def test_context_with_bg(self):
        mem = ConversationMemory()
        mem._bg = "用户询问了天气和新闻"
        ctx = mem.get_context()
        assert "[历史背景]" in ctx
        assert "天气" in ctx

    def test_mid_eviction_on_overflow(self):
        mem = ConversationMemory(max_short_turns=1, max_mid_entries=2)
        for i in range(5):
            mem.add_turn(f"问{i}", f"答{i}")
        assert mem.mid_count <= 2


class TestLLMCompression:
    """async LLM 压缩方法"""

    def test_compress_mid_calls_llm(self):
        mem = ConversationMemory(max_short_turns=1)
        mem.add_turn("第1轮", "回复1")
        mem.add_turn("第2轮", "回复2")
        mem.add_turn("第3轮", "回复3")

        assert mem.mid_count >= 1

        with patch("server.llm.ask_llm", new=AsyncMock(return_value="压缩摘要")):
            asyncio.run(mem.compress_mid())

        assert mem.mid_compressed
        assert "压缩摘要" in mem._mid[0]

    def test_compress_mid_noop_when_already_compressed(self):
        mem = ConversationMemory()
        mem._mid = ["已压缩"]
        mem._mid_compressed = True

        with patch("server.llm.ask_llm") as mock_llm:
            asyncio.run(mem.compress_mid())
            mock_llm.assert_not_called()

    def test_compress_background_sets_bg(self):
        mem = ConversationMemory()
        mem._mid = ["摘要1", "摘要2"]

        with patch("server.llm.ask_llm", new=AsyncMock(return_value="背景元摘要")):
            asyncio.run(mem.compress_background())

        assert mem.bg_summary == "背景元摘要"

    def test_compress_background_noop_when_no_mid(self):
        mem = ConversationMemory()

        with patch("server.llm.ask_llm") as mock_llm:
            asyncio.run(mem.compress_background())
            mock_llm.assert_not_called()

    def test_compress_background_truncates_to_max(self):
        mem = ConversationMemory(bg_max_chars=10)
        mem._mid = ["摘要"]

        with patch("server.llm.ask_llm", new=AsyncMock(return_value="这是一段非常长的背景元摘要文本")):
            asyncio.run(mem.compress_background())

        assert len(mem.bg_summary) <= 10


class TestProperties:
    def test_bg_summary_initially_empty(self):
        mem = ConversationMemory()
        assert mem.bg_summary == ""

    def test_turn_count_and_short_turns(self):
        mem = ConversationMemory(max_short_turns=1)
        mem.add_turn("a", "b")
        mem.add_turn("c", "d")
        assert mem.turn_count == 2
        assert mem.short_turns == 1


class TestEdgeCases:
    def test_single_turn_no_eviction(self):
        mem = ConversationMemory(max_short_turns=3)
        mem.add_turn("hello", "world")
        assert mem.short_turns == 1
        assert mem.mid_count == 0

    def test_exactly_at_boundary(self):
        mem = ConversationMemory(max_short_turns=3)
        mem.add_turn("1", "a")
        mem.add_turn("2", "b")
        mem.add_turn("3", "c")
        assert mem.short_turns == 3
        assert mem.mid_count == 0

    def test_one_over_boundary(self):
        mem = ConversationMemory(max_short_turns=3)
        mem.add_turn("1", "a")
        mem.add_turn("2", "b")
        mem.add_turn("3", "c")
        mem.add_turn("4", "d")
        assert mem.short_turns == 3
        assert mem.mid_count == 1

    def test_full_pipeline(self):
        """完整三层压缩管线"""
        mem = ConversationMemory(max_short_turns=2, max_mid_entries=3)

        with patch("server.llm.ask_llm", new=AsyncMock(return_value="压缩")):
            for i in range(8):
                mem.add_turn(f"问{i}", f"答{i}")
            asyncio.run(mem.compress_mid())
            asyncio.run(mem.compress_background())

        ctx = mem.get_context()
        assert mem.short_turns == 2
        assert mem.mid_count <= 3
        assert len(mem.bg_summary) > 0
        assert "[历史背景]" in ctx
