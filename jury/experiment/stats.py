"""
experiment/stats.py

投票統計計算器。

從 VotingRecord 列表計算整體統計摘要、
各職業類別分佈、各 OCEAN 維度高低投票傾向。
"""
from __future__ import annotations

from collections import defaultdict

from experiment.models import (
    VERDICT_ERROR,
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
    VotingRecord,
    VotingStats,
)

# OCEAN 五大維度名稱
# Five OCEAN dimension names
_OCEAN_DIMENSIONS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)


class StatsCalculator:
    """
    從 VotingRecord 列表計算統計摘要 VotingStats。

    計算內容：
      - 整體投票分佈（guilty / not_guilty / parse_error）
      - 各職業類別投票分佈
      - 各 OCEAN 維度高低對投票傾向的影響（high vs low，忽略 medium）
      - dominant_verdict（多數裁決方向；平局時選 guilty）
    """

    def calculate(self, records: list[VotingRecord]) -> VotingStats:
        """
        計算完整的統計摘要。

        Args:
            records: 所有個人投票記錄。

        Returns:
            VotingStats 統計摘要。
        """
        total      = len(records)
        valid      = [r for r in records if r.verdict != VERDICT_ERROR]
        guilty     = [r for r in valid if r.verdict == VERDICT_GUILTY]
        not_guilty = [r for r in valid if r.verdict == VERDICT_NOT_GUILTY]
        errors     = [r for r in records if r.verdict == VERDICT_ERROR]

        valid_n = len(valid) or 1  # 避免除以零

        # 平局時選 guilty（≥ 條件）
        # Tie goes to guilty (using >= condition)
        dominant_verdict = (
            VERDICT_GUILTY if len(guilty) >= len(not_guilty) else VERDICT_NOT_GUILTY
        )

        return VotingStats(
            total=total,
            guilty_count=len(guilty),
            not_guilty_count=len(not_guilty),
            parse_error_count=len(errors),
            guilty_rate=len(guilty) / valid_n,
            not_guilty_rate=len(not_guilty) / valid_n,
            dominant_verdict=dominant_verdict,
            by_occupation_category=self._by_occupation(records),
            by_ocean_dimension=self._by_ocean(records),
        )

    def _by_occupation(self, records: list[VotingRecord]) -> dict:
        """計算各職業類別的投票分佈（排除 parse_error）。"""
        buckets: dict[str, dict] = defaultdict(
            lambda: {"guilty": 0, "not_guilty": 0, "total": 0}
        )
        for r in records:
            if r.verdict == VERDICT_ERROR:
                continue
            b = buckets[r.occupation_category]
            b["total"] += 1
            b[r.verdict] += 1

        result = {}
        for cat, b in sorted(buckets.items()):
            n = b["total"] or 1
            result[cat] = {
                "guilty_count": b["guilty"],
                "not_guilty_count": b["not_guilty"],
                "total": b["total"],
                "guilty_rate": round(b["guilty"] / n, 4),
                "not_guilty_rate": round(b["not_guilty"] / n, 4),
            }
        return result

    def _by_ocean(self, records: list[VotingRecord]) -> dict:
        """計算各 OCEAN 維度高低對投票傾向的影響（只比較 high vs low）。"""
        result = {}
        for dim in _OCEAN_DIMENSIONS:
            high_records = [
                r for r in records
                if r.ocean_profile.get(dim) == "high" and r.verdict != VERDICT_ERROR
            ]
            low_records = [
                r for r in records
                if r.ocean_profile.get(dim) == "low" and r.verdict != VERDICT_ERROR
            ]
            result[dim] = {
                "high": _rate_summary(high_records),
                "low": _rate_summary(low_records),
            }
        return result


def _rate_summary(records: list[VotingRecord]) -> dict:
    """計算一組記錄的 guilty/not_guilty 比例摘要。"""
    total        = len(records) or 1
    guilty_n     = sum(1 for r in records if r.verdict == VERDICT_GUILTY)
    not_guilty_n = len(records) - guilty_n
    return {
        "count": len(records),
        "guilty_count": guilty_n,
        "not_guilty_count": not_guilty_n,
        "guilty_rate": round(guilty_n / total, 4),
        "not_guilty_rate": round(not_guilty_n / total, 4),
    }
