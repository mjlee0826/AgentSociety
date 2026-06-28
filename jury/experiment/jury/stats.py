"""
experiment/jury/stats.py

陪審團投票統計計算器。

設計原則：
  StatsCalculator 繼承 BaseStatsCalculator，固定使用 JURY_SCHEMA，
  輸入 list[VotingRecord]，輸出 VotingStats。

  共用的 _by_occupation_raw() / _by_ocean_raw() 由基類提供；
  此模組只負責組裝 VotingStats（guilty/not_guilty 分佈）。
"""
from __future__ import annotations

from experiment.shared.schemas import JURY_SCHEMA
from experiment.shared.stats import BaseStatsCalculator
from experiment.jury.models import (
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
    VotingRecord,
    VotingStats,
)


class StatsCalculator(BaseStatsCalculator):
    """
    從 VotingRecord 列表計算統計摘要 VotingStats。

    繼承 BaseStatsCalculator，固定使用 JURY_SCHEMA（guilty / not_guilty）。

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
        choices     = JURY_SCHEMA.valid_choices   # ["guilty", "not_guilty"]
        error_value = JURY_SCHEMA.error_value     # "parse_error"

        counts    = self._count_decisions(records, choices, error_value)
        by_occ    = self._by_occupation_raw(records, choices, error_value)
        by_ocean  = self._by_ocean_raw(records, choices, error_value)

        total        = len(records)
        guilty_n     = counts[VERDICT_GUILTY]
        not_guilty_n = counts[VERDICT_NOT_GUILTY]
        error_n      = counts[error_value]
        valid_n      = guilty_n + not_guilty_n or 1  # 避免除以零

        # 平局時選 guilty（≥ 條件）
        # Tie goes to guilty (using >= condition)
        dominant_verdict = (
            VERDICT_GUILTY if guilty_n >= not_guilty_n else VERDICT_NOT_GUILTY
        )

        return VotingStats(
            total=total,
            guilty_count=guilty_n,
            not_guilty_count=not_guilty_n,
            parse_error_count=error_n,
            guilty_rate=guilty_n / valid_n,
            not_guilty_rate=not_guilty_n / valid_n,
            dominant_verdict=dominant_verdict,
            by_occupation_category=by_occ,
            by_ocean_dimension=by_ocean,
        )
