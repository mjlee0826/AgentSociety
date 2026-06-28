"""
experiment/shared/schemas.py

決策格式規格定義。

設計原則：
  DecisionSchema 是參數化 ResponseParser 與 BaseStatsCalculator 的核心抽象。
  預定義的 JURY_SCHEMA 與 BYSTANDER_SCHEMA 供各實驗模組直接引用，
  不需在每個模組中重新定義。

  新增實驗類型時，在此建立新的 DecisionSchema 實例即可，
  不需修改 ResponseParser 或 BaseStatsCalculator。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DecisionSchema:
    """
    決策格式規格 — 定義 Agent 回應中決策欄位的名稱與合法選項。

    用於參數化 ResponseParser、BaseStatsCalculator、BaseReliabilityCalculator，
    使不同實驗共用同一套解析與統計基礎設施：
      - 陪審團實驗：field_name="VERDICT", valid_choices=["guilty", "not_guilty"]
      - 煙霧房實驗：field_name="ACTION",  valid_choices=["report", "wait", "ignore"]

    設計原則：
      - 新增實驗類型時，只需建立新的 DecisionSchema 實例，不需修改下游模組
      - 預定義的 JURY_SCHEMA / BYSTANDER_SCHEMA 供各實驗模組直接引用

    Attributes:
        field_name:    Agent 回應中的欄位名稱（大寫，如 "VERDICT" 或 "ACTION"）
        valid_choices: 合法的決策值列表（小寫）
        error_value:   解析失敗時的預設值（預設 "parse_error"）
    """

    field_name:    str
    valid_choices: list[str] = field(default_factory=list)
    error_value:   str = "parse_error"


# ── 預定義 Schema 實例（供各實驗模組直接引用）
# Pre-defined schema instances (for direct use in experiment modules)

JURY_SCHEMA = DecisionSchema(
    field_name    = "VERDICT",
    valid_choices = ["guilty", "not_guilty"],
    # 陪審團裁決：有罪 / 無罪
    # Jury verdict: guilty or not_guilty
)

BYSTANDER_SCHEMA = DecisionSchema(
    field_name    = "ACTION",
    valid_choices = ["report", "wait", "ignore"],
    # 旁觀者行動：通報 / 等待 / 忽略
    # Bystander action: report the smoke / wait and observe / ignore it
)
