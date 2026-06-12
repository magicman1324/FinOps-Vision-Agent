"""三层渐进式语义压缩记忆 — 短窗口 + 中距摘要 + 背景元摘要"""

import logging

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    三层记忆：
    - short: 最近 max_short 轮完整对话（精确文本）
    - mid: 中距轮次的结构化摘要列表（LLM 压缩）
    - background: 远距元摘要（≤150 字，LLM 压缩）
    """

    def __init__(
        self,
        max_short_turns: int = 3,
        max_mid_entries: int = 7,
        bg_max_chars: int = 150,
    ):
        self._short: list[dict] = []  # [{"role": str, "content": str}]
        self._mid: list[str] = []     # 摘要字符串
        self._bg: str = ""            # 元摘要
        self._max_short = max_short_turns
        self._max_mid = max_mid_entries
        self._bg_max = bg_max_chars
        self._turn_count = 0

    def add_turn(self, user_text: str, assistant_text: str):
        """添加一轮对话"""
        self._turn_count += 1
        self._short.append({"role": "user", "content": user_text})
        self._short.append({"role": "assistant", "content": assistant_text})
        self._evict_short()

    def _evict_short(self):
        """短窗口溢出 → 推入中距摘要"""
        while len(self._short) > self._max_short * 2:
            oldest_user = self._short.pop(0)
            oldest_asst = self._short.pop(0)
            summary = f"用户: {oldest_user['content']} | AI: {oldest_asst['content']}"
            self._add_mid(summary)

    def _add_mid(self, summary: str):
        """中距摘要溢出 → 压缩入背景"""
        self._mid.append(summary)
        while len(self._mid) > self._max_mid:
            self._mid.pop(0)

    def get_context(self) -> str:
        """
        组装上下文文本，可注入 system prompt。
        格式: [背景] [中距摘要]... [近期对话]
        """
        parts = []
        if self._bg:
            parts.append(f"[历史背景] {self._bg}")
        for s in self._mid:
            parts.append(f"[之前] {s}")
        for msg in self._short:
            prefix = "用户" if msg["role"] == "user" else "AI"
            parts.append(f"{prefix}: {msg['content']}")
        return "\n".join(parts)

    def get_short_history(self) -> list[dict]:
        """返回短窗口消息列表，可直接作为 LLM messages"""
        return list(self._short)

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def short_turns(self) -> int:
        return len(self._short) // 2

    @property
    def mid_count(self) -> int:
        return len(self._mid)

    @property
    def bg_summary(self) -> str:
        return self._bg
