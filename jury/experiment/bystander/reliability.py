"""
experiment/bystander/reliability.py

煙霧實驗個人決策可靠性計算器。

設計原則：
  SmokeReliabilityCalculator 繼承 BaseReliabilityCalculator，
  固定使用 BYSTANDER_SCHEMA，輸入 list[SmokeDecisionRecord]，
  輸出 ReliabilityStatsBase。

  平行於 jury/reliability.py 的 ReliabilityCalculator，差異只在 schema。
  所有計算邏輯（modal agreement、bucketize、by_occupation、by_ocean）
  均由基類 BaseReliabilityCalculator 提供。
"""
from __future__ import annotations

from experiment.shared.reliability import BaseReliabilityCalculator, ReliabilityStatsBase
from experiment.shared.schemas import BYSTANDER_SCHEMA
from experiment.bystander.models import SmokeDecisionRecord


class SmokeReliabilityCalculator(BaseReliabilityCalculator):
    """
    從 N 次重複測量的 SmokeDecisionRecord 計算 reliability 統計。

    繼承 BaseReliabilityCalculator，固定使用 BYSTANDER_SCHEMA（report/wait/ignore）。
    平行於 jury/reliability.py 的 ReliabilityCalculator。

    流程（由基類提供）：
      1. 依 persona_id groupby 收集所有重複測量
      2. 對每個 persona 計算 modal decision / modal agreement / confidence SD
      3. 聚合成整體指標，並按 occupation_category、OCEAN 維度切片
    """

    def calculate(
        self,
        records: list[SmokeDecisionRecord],
        repeat_n: int,
    ) -> ReliabilityStatsBase:
        """
        計算 reliability 統計。

        Args:
            records:  含 run_index 的所有煙霧決策記錄；同一 persona_id 應有多筆。
            repeat_n: 實驗設計上每 persona 預計的重複次數。

        Returns:
            ReliabilityStatsBase 摘要（domain-neutral，jury/bystander 共用格式）。
        """
        return super().calculate(records, repeat_n, BYSTANDER_SCHEMA)
