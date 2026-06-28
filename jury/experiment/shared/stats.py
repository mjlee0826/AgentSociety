"""
experiment/shared/stats.py

共用統計計算基類。

設計原則：
  BaseStatsCalculator 封裝「按職業類別 / OCEAN 維度分群計算決策分佈」
  的共用邏輯，jury/stats.py（StatsCalculator）與
  bystander/stats.py（SmokeStatsCalculator）都繼承此基類。

  前提：records 需有 .decision、.occupation_category、.ocean_profile 屬性。
  VotingRecord 透過 @property decision（alias for verdict）符合此介面。

  子類別實作 calculate() 方法，呼叫 _raw methods 取得 dict 後，
  轉換成各自的 typed 統計摘要物件（VotingStats 或 SmokeDecisionStats）。
"""
from __future__ import annotations

from collections import defaultdict

# OCEAN 五大維度名稱
# Five OCEAN dimension names
_OCEAN_DIMENSIONS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)

# 浮點數精度
_FLOAT_PRECISION = 4


class BaseStatsCalculator:
    """
    共用統計計算基類。

    Records 需有以下屬性：
      - .decision:            str（決策值，如 "guilty" / "report"）
      - .occupation_category: str（職業類別）
      - .ocean_profile:       dict（{"openness": "high"|"medium"|"low", ...}）

    子類別實作 calculate(records) → typed 統計物件。
    """

    def _count_decisions(
        self,
        records: list,
        choices: list[str],
        error_value: str,
    ) -> dict[str, int]:
        """
        計算各選項的出現次數。

        Args:
            records:     決策記錄列表（需有 .decision 屬性）。
            choices:     合法決策選項列表（不含 error_value）。
            error_value: 解析失敗時的決策值。

        Returns:
            {choice: count, error_value: count} 字典。
        """
        counts: dict[str, int] = {c: 0 for c in choices}
        counts[error_value] = 0
        for r in records:
            key = r.decision if r.decision in counts else error_value
            counts[key] += 1
        return counts

    def _by_occupation_raw(
        self,
        records: list,
        choices: list[str],
        error_value: str,
    ) -> dict:
        """
        按職業類別計算決策分佈（raw dict，以 choice 為 key）。

        排除 parse_error 記錄後計算各職業類別的決策分佈與比例。

        Args:
            records:     決策記錄列表。
            choices:     合法決策選項列表。
            error_value: 解析失敗的決策值（排除在計算之外）。

        Returns:
            {occupation_category: {choice: count, "{choice}_rate": float, "total": int}}
        """
        # 初始化各職業類別的計數桶
        buckets: dict[str, dict] = defaultdict(
            lambda: {c: 0 for c in choices} | {"total": 0}
        )
        for r in records:
            if r.decision == error_value:
                continue  # 排除解析失敗記錄
            b = buckets[r.occupation_category]
            b["total"] += 1
            if r.decision in b:
                b[r.decision] += 1

        result = {}
        for cat, b in sorted(buckets.items()):
            n = b["total"] or 1
            entry = {"total": b["total"]}
            for c in choices:
                entry[f"{c}_count"] = b[c]
                entry[f"{c}_rate"]  = round(b[c] / n, _FLOAT_PRECISION)
            result[cat] = entry
        return result

    def _by_ocean_raw(
        self,
        records: list,
        choices: list[str],
        error_value: str,
    ) -> dict:
        """
        按 OCEAN 維度高低計算決策分佈（raw dict）。

        對每個 OCEAN 維度，分別取「high」和「low」的記錄（忽略 medium），
        計算各決策選項的分佈比例。

        Args:
            records:     決策記錄列表。
            choices:     合法決策選項列表。
            error_value: 解析失敗的決策值（排除在計算之外）。

        Returns:
            {dimension: {high: {count, {choice}_count, {choice}_rate}, low: {...}}}
        """
        result = {}
        for dim in _OCEAN_DIMENSIONS:
            high_records = [
                r for r in records
                if r.ocean_profile.get(dim) == "high" and r.decision != error_value
            ]
            low_records = [
                r for r in records
                if r.ocean_profile.get(dim) == "low" and r.decision != error_value
            ]
            result[dim] = {
                "high": self._rate_summary_raw(high_records, choices),
                "low":  self._rate_summary_raw(low_records, choices),
            }
        return result

    def _rate_summary_raw(self, records: list, choices: list[str]) -> dict:
        """
        計算一組記錄的各決策比例摘要（raw dict）。

        Args:
            records: 已過濾掉 error 的記錄列表。
            choices: 合法決策選項列表。

        Returns:
            {count: int, {choice}_count: int, {choice}_rate: float}
        """
        total = len(records) or 1
        entry = {"count": len(records)}
        for c in choices:
            c_n = sum(1 for r in records if r.decision == c)
            entry[f"{c}_count"] = c_n
            entry[f"{c}_rate"]  = round(c_n / total, _FLOAT_PRECISION)
        return entry
