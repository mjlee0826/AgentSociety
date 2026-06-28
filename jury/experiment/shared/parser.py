"""
experiment/shared/parser.py

Agent 回應解析器。

負責從 TinyPerson 的原始回應文字中提取決策欄位 / CONFIDENCE / REASON 三個欄位。
接受 DecisionSchema 參數，使解析規則與決策類型解耦：
  - 陪審團實驗：ResponseParser()                → 預設 JURY_SCHEMA，解析 VERDICT 欄位
  - 煙霧房實驗：ResponseParser(BYSTANDER_SCHEMA) → 解析 ACTION 欄位

向後相容保證：
  ResponseParser() 無參數呼叫行為與重構前完全相同（預設 JURY_SCHEMA）。
  現有呼叫端（voter.py、group_deliberation.py）零需要修改。
"""
from __future__ import annotations

import re

from experiment.shared.schemas import DecisionSchema, JURY_SCHEMA


class ResponseParser:
    """
    解析 Agent 回應，提取決策欄位 / CONFIDENCE / REASON。

    接受 DecisionSchema 參數，使解析規則與決策類型解耦。
    預設使用 JURY_SCHEMA，向後相容所有現有程式碼。

    Attributes:
        _schema:           決策格式規格（決定欄位名稱與合法選項）。
        _decision_pattern: 從 schema 動態生成的決策欄位 regex。
        _reason_pattern:   從 schema 動態生成的 REASON 結束邊界 regex。
    """

    # CONFIDENCE 解析模式（與決策類型無關，固定不變）
    _CONFIDENCE_PATTERN = re.compile(
        r"CONFIDENCE\s*:\s*(\d+)", re.IGNORECASE
    )

    # CONFIDENCE 合法範圍
    _CONFIDENCE_MIN = 1
    _CONFIDENCE_MAX = 10

    def __init__(self, schema: DecisionSchema = JURY_SCHEMA) -> None:
        """
        建立 ResponseParser 實例。

        Args:
            schema: 決策格式規格；預設 JURY_SCHEMA（VERDICT: guilty/not_guilty）。
                    傳入 BYSTANDER_SCHEMA 可解析 ACTION: report/wait/ignore。
        """
        self._schema = schema

        # 從 schema 動態建立決策欄位的 regex pattern
        # Dynamically build decision field regex from schema
        choices_re = "|".join(re.escape(c) for c in schema.valid_choices)
        self._decision_pattern = re.compile(
            rf"{re.escape(schema.field_name)}\s*:\s*({choices_re})",
            re.IGNORECASE,
        )

        # REASON 結束邊界需跟著 field_name 動態生成
        # (避免把下一個 VERDICT/ACTION 行誤判為 REASON 的一部分)
        # REASON ending boundary must be built dynamically to avoid
        # mistaking next VERDICT/ACTION line as part of REASON
        self._reason_pattern = re.compile(
            rf"REASON\s*:\s*(.+?)(?=\n{re.escape(schema.field_name)}|\nCONFIDENCE|\Z)",
            re.IGNORECASE | re.DOTALL,
        )

    def parse(self, text: str) -> tuple[str, int, str]:
        """
        從回應文字中提取 (decision, confidence, reason)。

        Args:
            text: Agent 的原始回應文字。

        Returns:
            (decision, confidence, reason) tuple。
            決策欄位缺失時：decision=schema.error_value、confidence=-1、reason=原始文字。
            CONFIDENCE 缺失時：confidence=-1，但 decision 仍有效。
            REASON 缺失時：reason=''。
        """
        decision_match   = self._decision_pattern.search(text)
        confidence_match = self._CONFIDENCE_PATTERN.search(text)
        reason_match     = self._reason_pattern.search(text)

        if not decision_match:
            # 決策欄位解析失敗，回傳 error_value
            # Decision field parsing failed, return error_value
            return self._schema.error_value, -1, text

        decision   = decision_match.group(1).lower()
        confidence = int(confidence_match.group(1)) if confidence_match else -1
        reason     = reason_match.group(1).strip() if reason_match else ""

        # 將 confidence 截斷至合法範圍
        # Clamp confidence to valid range
        if confidence != -1:
            confidence = max(self._CONFIDENCE_MIN, min(self._CONFIDENCE_MAX, confidence))

        return decision, confidence, reason
