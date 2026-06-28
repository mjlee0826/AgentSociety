"""
experiment/bystander 子套件 — 旁觀者效應實驗模組。

平行於 experiment/jury 套件，適配煙霧情境（report/wait/ignore 三選項）。

公開介面：
  SmokeDecisionRecord       — 個人煙霧決策記錄
  SmokeDecisionStats        — 整體煙霧決策統計摘要
  SMOKE_DECISION_REPORT     — 決策常數：通報
  SMOKE_DECISION_WAIT       — 決策常數：等待
  SMOKE_DECISION_IGNORE     — 決策常數：忽略
  SMOKE_DECISION_ERROR      — 決策常數：解析失敗
  BystanderRoundRecord      — 群體討論逐輪記錄
  BystanderAgentSummary     — 單一 Agent 跨輪次摘要
  BystanderGroupStats       — 群體討論整體統計摘要
  SmokeStatsCalculator      — 煙霧決策統計計算器
  SmokeReliabilityCalculator — 煙霧決策可靠性計算器
  SmokePersonaVoter         — 個人煙霧決策 Agent
  SmokeIndividualVotingRunner — 煙霧個人決策實驗執行入口
  SmokeGroupDeliberationRunner — 旁觀者效應群體實驗執行入口
"""

from experiment.bystander.models import (
    SmokeDecisionRecord,
    SmokeDecisionStats,
    SMOKE_DECISION_REPORT,
    SMOKE_DECISION_WAIT,
    SMOKE_DECISION_IGNORE,
    SMOKE_DECISION_ERROR,
)
from experiment.bystander.group_models import (
    BystanderRoundRecord,
    BystanderAgentSummary,
    BystanderGroupStats,
)
from experiment.bystander.stats import SmokeStatsCalculator
from experiment.bystander.reliability import SmokeReliabilityCalculator
from experiment.bystander.voter import SmokePersonaVoter
from experiment.bystander.individual_voting import SmokeIndividualVotingRunner
from experiment.bystander.group_deliberation import SmokeGroupDeliberationRunner

__all__ = [
    "SmokeDecisionRecord",
    "SmokeDecisionStats",
    "SMOKE_DECISION_REPORT",
    "SMOKE_DECISION_WAIT",
    "SMOKE_DECISION_IGNORE",
    "SMOKE_DECISION_ERROR",
    "BystanderRoundRecord",
    "BystanderAgentSummary",
    "BystanderGroupStats",
    "SmokeStatsCalculator",
    "SmokeReliabilityCalculator",
    "SmokePersonaVoter",
    "SmokeIndividualVotingRunner",
    "SmokeGroupDeliberationRunner",
]
