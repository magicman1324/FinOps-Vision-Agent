"""三层渐进式语义压缩记忆 — 短窗口 + 中距摘要 + 背景元摘要"""

import asyncio
import logging

logger = logging.getLogger(__name__)

MID_COMPRESS_PROMPT = "将以下对话回合压缩为一句结构化摘要，保留关键实体、动作和属性，不超过40字。"

BG_COMPRESS_PROMPT = "将以下多条对话摘要进一步压缩为一条元摘要，不超过150字，突出最核心的主题和信息。"


class ConversationMemory:
    """
    三层记忆：
    - short: 最近 max_short 轮完整对话（精确文本）
    - mid: 中距轮次摘要列表（raw 或 LLM 压缩）
    - background: 远距元摘要（≤150 字，LLM 压缩）
    """

    def __init__(
        self,
        max_short_turns: int = 3,
        max_mid_entries: int = 7,
        bg_max_chars: int = 150,
    ):
        self._short: list[dict] = []
        self._mid: list[str] = []
        self._mid_compressed: bool = False  # mid 是否已压缩
        self._bg: str = ""
        self._max_short = max_short_turns
        self._max_mid = max_mid_entries
        self._bg_max = bg_max_chars
        self._turn_count = 0
        self._lock = asyncio.Lock()

    # ---- 写入 ----

    def add_turn(self, user_text: str, assistant_text: str):
        """添加一轮对话"""
        self._turn_count += 1
        self._short.append({"role": "user", "content": user_text})
        self._short.append({"role": "assistant", "content": assistant_text})
        self._evict_short()

    def _evict_short(self):
        """短窗口溢出 → 原始文本推入中距"""
        while len(self._short) > self._max_short * 2:
            oldest_user = self._short.pop(0)
            oldest_asst = self._short.pop(0)
            raw = f"用户: {oldest_user['content']} | AI: {oldest_asst['content']}"
            self._add_mid(raw)

    def _add_mid(self, entry: str):
        """中距溢出 → 最旧条目丢弃"""
        self._mid.append(entry)
        self._mid_compressed = False
        while len(self._mid) > self._max_mid:
            self._mid.pop(0)

    # ---- LLM 压缩（异步） ----

    async def compress_mid(self):
        """将中距 raw 条目压缩为结构化摘要"""
        if not self._mid or self._mid_compressed:
            return
        from server.llm import ask_llm

        async with self._lock:
            # 双重检查：锁内再次确认状态
            if not self._mid or self._mid_compressed:
                return
            entries = list(self._mid)
            new_mid = []
            any_compressed = False
            for entry in entries:
                try:
                    compressed = await ask_llm(entry, system_prompt=MID_COMPRESS_PROMPT)
                    new_mid.append(compressed.strip())
                    any_compressed = True
                except Exception:
                    logger.warning("compress_mid failed for entry, keeping raw")
                    new_mid.append(entry)
            self._mid = new_mid
            if any_compressed:
                self._mid_compressed = True
            logger.info("compress_mid done: %d entries", len(self._mid))

    async def compress_background(self):
        """将中距摘要压缩为背景元摘要"""
        if not self._mid:
            return
        from server.llm import ask_llm

        combined = "\n".join(self._mid)
        try:
            bg = await ask_llm(combined, system_prompt=BG_COMPRESS_PROMPT)
            self._bg = bg.strip()[: self._bg_max]
            logger.info("compress_background done: bg=%r", self._bg[:80])
        except Exception:
            logger.warning("compress_background failed")

    # ---- 读取 ----

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

    # ---- 属性 ----

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
    def mid_compressed(self) -> bool:
        return self._mid_compressed

    @property
    def bg_summary(self) -> str:
        return self._bg
