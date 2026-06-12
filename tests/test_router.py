"""测试双层意图路由 — L0 关键词 + L1 LLM 二分类"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from server.router import classify_intent, classify_intent_l0, classify_intent_l1


class TestL0VisualHits:
    """L0 命中视觉意图"""

    def test_object_identification(self):
        assert classify_intent_l0("这是什么") == "visual"
        assert classify_intent_l0("这是什么东西") == "visual"
        assert classify_intent_l0("那是谁") == "visual"

    def test_color_inquiry(self):
        assert classify_intent_l0("这是什么颜色") == "visual"
        assert classify_intent_l0("啥颜色") == "visual"
        assert classify_intent_l0("什么形状") == "visual"

    def test_appearance(self):
        assert classify_intent_l0("它长什么样") == "visual"
        assert classify_intent_l0("长什么样子的") == "visual"
        assert classify_intent_l0("外观怎么样") == "visual"

    def test_spatial(self):
        assert classify_intent_l0("杯子在哪里") == "visual"
        assert classify_intent_l0("钥匙在哪") == "visual"
        assert classify_intent_l0("钱包在哪儿") == "visual"

    def test_counting_objects(self):
        assert classify_intent_l0("桌上有几个杯子") == "visual"
        assert classify_intent_l0("这里多少个") == "visual"
        assert classify_intent_l0("还有多少张纸") == "visual"

    def test_perception_verbs(self):
        assert classify_intent_l0("你看到了什么") == "visual"
        assert classify_intent_l0("你看见那个红色的了吗") == "visual"

    def test_image_media_reference(self):
        assert classify_intent_l0("画面里有什么") == "visual"
        assert classify_intent_l0("这张图片内容是什么") == "visual"
        assert classify_intent_l0("屏幕上显示了什么") == "visual"

    def test_deictic_with_object(self):
        assert classify_intent_l0("这个东西是什么") == "visual"
        assert classify_intent_l0("那个颜色对吗") == "visual"

    def test_hand_egocentric(self):
        assert classify_intent_l0("我手里拿的是什么") == "visual"
        assert classify_intent_l0("我面前的是什么东西") == "visual"
        assert classify_intent_l0("桌子上有什么") == "visual"

    def test_show_request(self):
        assert classify_intent_l0("你能展示一下吗") == "visual"
        assert classify_intent_l0("显示给我看") == "visual"


class TestL0TextualMisses:
    """L0 未命中"""

    def test_greeting(self):
        assert classify_intent_l0("你好") == "textual"
        assert classify_intent_l0("早上好") == "textual"

    def test_general_question(self):
        assert classify_intent_l0("今天天气怎么样") == "textual"
        assert classify_intent_l0("现在几点") == "textual"

    def test_casual_conversation(self):
        assert classify_intent_l0("讲个笑话吧") == "textual"
        assert classify_intent_l0("介绍一下你自己") == "textual"

    def test_chitchat_with_see_word(self):
        assert classify_intent_l0("你觉得呢") == "textual"
        assert classify_intent_l0("你看这样行吗") == "textual"


class TestL0EdgeCases:
    def test_empty_string(self):
        assert classify_intent_l0("") == "textual"

    def test_whitespace_only(self):
        assert classify_intent_l0("   ") == "textual"

    def test_english_visual(self):
        assert classify_intent_l0("what is this") == "textual"


class TestL1LLMClassification:
    """L1 LLM 二分类"""

    def test_returns_visual_when_llm_says_visual(self):
        with patch("server.llm.ask_llm", new=AsyncMock(return_value="visual")):
            result = asyncio.run(classify_intent_l1("我手里这东西贵吗"))
            assert result == "visual"

    def test_returns_textual_when_llm_says_textual(self):
        with patch("server.llm.ask_llm", new=AsyncMock(return_value="textual")):
            result = asyncio.run(classify_intent_l1("今天天气怎么样"))
            assert result == "textual"

    def test_handles_llm_with_extra_whitespace(self):
        with patch("server.llm.ask_llm", new=AsyncMock(return_value="  visual  ")):
            result = asyncio.run(classify_intent_l1("这是啥"))
            assert result == "visual"

    def test_handles_llm_with_punctuation(self):
        with patch("server.llm.ask_llm", new=AsyncMock(return_value="visual。")):
            result = asyncio.run(classify_intent_l1("这什么东西"))
            assert result == "visual"

    def test_boundary_sentence_visual(self):
        # 边界句：口语化视觉提问，L0 可能漏
        with patch("server.llm.ask_llm", new=AsyncMock(return_value="visual")):
            result = asyncio.run(classify_intent_l1("诶这东西看着挺贵"))
            assert result == "visual"


class TestBackwardCompat:
    """向后兼容：classify_intent 仍可用"""

    def test_alias_works(self):
        assert classify_intent("这是什么") == "visual"
        assert classify_intent("你好") == "textual"
