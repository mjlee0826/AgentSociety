"""
experiment/parser.py

Agent 回應解析器。

負責從 TinyPerson 的原始回應文字中提取
VERDICT / CONFIDENCE / REASON 三個欄位。
設計為純靜態工具，無 LLM 呼叫，方便單元測試。
"""
from __future__ import annotations

import re

from experiment.models import VERDICT_ERROR, VERDICT_GUILTY, VERDICT_NOT_GUILTY


class ResponseParser:
    """
    解析 Agent 回應，提取 VERDICT / CONFIDENCE / REASON。

    設計為純靜態工具，方便單元測試。
    所有方法均為 classmethod，不需要實例化。
    """

    # 正規表達式模式
    _VERDICT_PATTERN = re.compile(
        r"VERDICT\s*:\s*(guilty|not_guilty)", re.IGNORECASE
    )
    _CONFIDENCE_PATTERN = re.compile(
        r"CONFIDENCE\s*:\s*(\d+)", re.IGNORECASE
    )
    _REASON_PATTERN = re.compile(
        r"REASON\s*:\s*(.+?)(?=\nVERDICT|\nCONFIDENCE|\Z)", re.IGNORECASE | re.DOTALL
    )

    # CONFIDENCE 合法範圍
    _CONFIDENCE_MIN = 1
    _CONFIDENCE_MAX = 10

    @classmethod
    def parse(cls, text: str) -> tuple[str, int, str]:
        """
        從回應文字中提取 (verdict, confidence, reason)。

        Args:
            text: Agent 的原始回應文字。

        Returns:
            (verdict, confidence, reason)。
            VERDICT 缺失時 verdict='parse_error'、confidence=-1。
            CONFIDENCE 缺失時 confidence=-1，但 verdict 仍有效。
            REASON 缺失時 reason=''。
        """
        verdict_match    = cls._VERDICT_PATTERN.search(text)
        confidence_match = cls._CONFIDENCE_PATTERN.search(text)
        reason_match     = cls._REASON_PATTERN.search(text)

        if not verdict_match:
            return VERDICT_ERROR, -1, text

        verdict    = verdict_match.group(1).lower()
        confidence = int(confidence_match.group(1)) if confidence_match else -1
        reason     = reason_match.group(1).strip() if reason_match else ""

        # 將 confidence 截斷至合法範圍
        # Clamp confidence to valid range
        if confidence != -1:
            confidence = max(cls._CONFIDENCE_MIN, min(cls._CONFIDENCE_MAX, confidence))

        return verdict, confidence, reason
