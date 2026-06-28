"""
experiment/jury/reliability.py

陪審團投票可靠性計算器。

設計原則：
  ReliabilityCalculator 繼承 BaseReliabilityCalculator，
  固定使用 JURY_SCHEMA，輸入 list[VotingRecord]，
  輸出 ReliabilityStatsBase。

  所有計算邏輯由基類 BaseReliabilityCalculator 提供，
  此模組只負責固定 schema 後委派給基類。
"""
from __future__ import annotations

from experiment.shared.reliability import BaseReliabilityCalculator, ReliabilityStatsBase
from experiment.shared.schemas import JURY_SCHEMA
from experiment.jury.models import VotingRecord


class ReliabilityCalculator(BaseReliabilityCalculator):
    """
    從 N 次重複測量的 VotingRecord 計算 reliability 統計。

    繼承 BaseReliabilityCalculator，固定使用 JURY_SCHEMA。

    流程：
      1. 依 persona_id groupby 收集所有重複測量
      2. 對每個 persona 計算 modal decision / modal agreement / confidence SD
      3. 聚合成整體指標，並按 occupation_category、OCEAN 維度切片
    """

    def calculate(
        self,
        records: list[VotingRecord],
        repeat_n: int,
    ) -> ReliabilityStatsBase:
        """
        計算 reliability 統計。

        Args:
            records:  含 run_index 的所有投票記錄；同一 persona_id 應有多筆。
            repeat_n: 實驗設計上每 persona 預計的重複次數。

        Returns:
            ReliabilityStatsBase 摘要。
        """
        return super().calculate(records, repeat_n, JURY_SCHEMA)
