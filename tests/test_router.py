"""测试 L0 关键词意图路由"""

import pytest

from server.router import classify_intent


class TestVisualHits:
    """命中视觉意图 — 应返回 'visual'"""

    def test_object_identification(self):
        assert classify_intent("这是什么") == "visual"
        assert classify_intent("这是什么东西") == "visual"
        assert classify_intent("那是谁") == "visual"

    def test_color_inquiry(self):
        assert classify_intent("这是什么颜色") == "visual"
        assert classify_intent("啥颜色") == "visual"
        assert classify_intent("什么形状") == "visual"

    def test_appearance(self):
        assert classify_intent("它长什么样") == "visual"
        assert classify_intent("长什么样子的") == "visual"
        assert classify_intent("外观怎么样") == "visual"

    def test_spatial(self):
        assert classify_intent("杯子在哪里") == "visual"
        assert classify_intent("钥匙在哪") == "visual"
        assert classify_intent("钱包在哪儿") == "visual"

    def test_counting_objects(self):
        assert classify_intent("桌上有几个杯子") == "visual"
        assert classify_intent("这里多少个") == "visual"
        assert classify_intent("还有多少张纸") == "visual"

    def test_perception_verbs(self):
        assert classify_intent("你看到了什么") == "visual"
        assert classify_intent("你看见那个红色的了吗") == "visual"
        assert classify_intent("你注意到了吗") == "visual"

    def test_image_media_reference(self):
        assert classify_intent("画面里有什么") == "visual"
        assert classify_intent("这张图片内容是什么") == "visual"
        assert classify_intent("屏幕上显示了什么") == "visual"
        assert classify_intent("摄像头拍到了什么") == "visual"

    def test_deictic_with_object(self):
        assert classify_intent("这个东西是什么") == "visual"
        assert classify_intent("那个颜色对吗") == "visual"
        assert classify_intent("这个人是男的还是女的") == "visual"

    def test_hand_egocentric(self):
        assert classify_intent("我手里拿的是什么") == "visual"
        assert classify_intent("我手上有什么") == "visual"
        assert classify_intent("我面前的是什么东西") == "visual"
        assert classify_intent("桌子上有什么") == "visual"

    def test_show_request(self):
        assert classify_intent("你能展示一下吗") == "visual"
        assert classify_intent("显示给我看") == "visual"


class TestTextualMisses:
    """未命中 — 应返回 'textual'"""

    def test_greeting(self):
        assert classify_intent("你好") == "textual"
        assert classify_intent("早上好") == "textual"

    def test_general_question(self):
        assert classify_intent("今天天气怎么样") == "textual"
        assert classify_intent("现在几点") == "textual"
        assert classify_intent("DeepSeek是什么") == "textual"

    def test_casual_conversation(self):
        assert classify_intent("讲个笑话吧") == "textual"
        assert classify_intent("帮我写一首诗") == "textual"
        assert classify_intent("介绍一下你自己") == "textual"

    def test_chitchat_with_see_word(self):
        # "看" 在口语化表达中常指"认为/看法"，不是视觉
        assert classify_intent("你觉得呢") == "textual"
        assert classify_intent("我怎么知道") == "textual"
        assert classify_intent("你看这样行吗") == "textual"


class TestEdgeCases:
    def test_empty_string(self):
        assert classify_intent("") == "textual"

    def test_whitespace_only(self):
        assert classify_intent("   ") == "textual"

    def test_english_visual(self):
        # 英文暂不支持，走 textual
        assert classify_intent("what is this") == "textual"
