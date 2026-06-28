"""
experiment/bystander/stats.py

煙霧實驗個人決策統計計算器。

設計原則：
  SmokeStatsCalculator 繼承 BaseStatsCalculator，固定使用 BYSTANDER_SCHEMA，
  輸入 list[SmokeDecisionRecord]，輸出 SmokeDecisionStats。

  平行於 jury/stats.py 的 StatsCalculator，差異在決策選項
  （report/wait/ignore 三選項，vs guilty/not_guilty 兩選項）。

  dominant_decision 為三選項中出現最多的決策；
  若有平局，優先順序為 report > wait > ignore（通報為最強訊號）。
"""
from __future__ import annotations

from experiment.shared.schemas import BYSTANDER_SCHEMA
from experiment.shared.stats import BaseStatsCalculator
from experiment.bystander.models import (
    SMOKE_DECISION_REPORT,
    SMOKE_DECISION_WAIT,
    SMOKE_DECISION_IGNORE,
    SmokeDecisionRecord,
    SmokeDecisionStats,
)

# 平局優先順序（通報為最強社會訊號）
# Tie-breaking priority (reporting is the strongest social signal)
_DOMINANCE_ORDER = [SMOKE_DECISION_REPORT, SMOKE_DECISION_WAIT, SMOKE_DECISION_IGNORE]


class SmokeStatsCalculator(BaseStatsCalculator):
    """
    從 SmokeDecisionRecord 列表計算統計摘要 SmokeDecisionStats。

    繼承 BaseStatsCalculator，固定使用 BYSTANDER_SCHEMA（report / wait / ignore）。
    平行於 jury/stats.py 的 StatsCalculator。

    計算內容：
      - 整體決策分佈（report / wait / ignore / parse_error）
      - 各職業類別決策分佈
      - 各 OCEAN 維度高低對決策傾向的影響（high vs low，忽略 medium）
      - dominant_decision（三選項多數決；平局時優先順序 report > wait > ignore）
    """

    def calculate(self, records: list[SmokeDecisionRecord]) -> SmokeDecisionStats:
        """
        計算完整的統計摘要。

        Args:
            records: 所有個人煙霧決策記錄。

        Returns:
            SmokeDecisionStats 統計摘要。
        """
        choices     = BYSTANDER_SCHEMA.valid_choices   # ["report", "wait", "ignore"]
        error_value = BYSTANDER_SCHEMA.error_value     # "parse_error"

        counts    = self._count_decisions(records, choices, error_value)
        by_occ    = self._by_occupation_raw(records, choices, error_value)
        by_ocean  = self._by_ocean_raw(records, choices, error_value)

        total     = len(records)
        report_n  = counts[SMOKE_DECISION_REPORT]
        wait_n    = counts[SMOKE_DECISION_WAIT]
        ignore_n  = counts[SMOKE_DECISION_IGNORE]
        error_n   = counts[error_value]
        valid_n   = report_n + wait_n + ignore_n or 1  # 避免除以零

        # 三選項多數決（平局時優先順序 report > wait > ignore）
        # Three-way majority decision (tie-breaking: report > wait > ignore)
        decision_counts = {
            SMOKE_DECISION_REPORT: report_n,
            SMOKE_DECISION_WAIT:   wait_n,
            SMOKE_DECISION_IGNORE: ignore_n,
        }
        dominant_decision = max(
            _DOMINANCE_ORDER,
            key=lambda d: (decision_counts[d], -_DOMINANCE_ORDER.index(d)),
        )

        return SmokeDecisionStats(
            total=total,
            report_count=report_n,
            wait_count=wait_n,
            ignore_count=ignore_n,
            parse_error_count=error_n,
            report_rate=report_n / valid_n,
            wait_rate=wait_n / valid_n,
            ignore_rate=ignore_n / valid_n,
            dominant_decision=dominant_decision,
            by_occupation_category=by_occ,
            by_ocean_dimension=by_ocean,
        )
