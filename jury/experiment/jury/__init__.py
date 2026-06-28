"""
experiment/jury 子套件 — 陪審團實驗模組。

公開介面：
  VotingRecord           — 個人投票記錄
  VotingStats            — 整體投票統計摘要
  VERDICT_GUILTY         — 裁決常數：有罪
  VERDICT_NOT_GUILTY     — 裁決常數：無罪
  VERDICT_ERROR          — 裁決常數：解析失敗
  AgentDeliberationRecord — 群體討論後單一 Agent 的投票記錄
  GroupDeliberationStats  — 群體討論整體統計摘要
  GroupSliceStats         — 切片統計（正常 / 暗樁子群）
  StatsCalculator        — 投票統計計算器
  ReliabilityCalculator  — 投票可靠性計算器
  PersonaVoter           — 個人投票 Agent
  BaselineResultsWriter  — baseline 結果持久化
  BaselineResultsReader  — baseline 結果讀取
  IndividualVotingRunner — Phase 2 個人投票實驗執行入口
  GroupDeliberationRunner — Phase 3 群體討論實驗執行入口
"""

from experiment.jury.models import (
    VotingRecord,
    VotingStats,
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
    VERDICT_ERROR,
)
from experiment.jury.group_models import (
    AgentDeliberationRecord,
    GroupDeliberationStats,
    GroupSliceStats,
)
from experiment.jury.stats import StatsCalculator
from experiment.jury.reliability import ReliabilityCalculator
from experiment.jury.voter import PersonaVoter
from experiment.jury.baseline import BaselineResultsWriter, BaselineResultsReader
from experiment.jury.individual_voting import IndividualVotingRunner
from experiment.jury.group_deliberation import GroupDeliberationRunner

__all__ = [
    "VotingRecord",
    "VotingStats",
    "VERDICT_GUILTY",
    "VERDICT_NOT_GUILTY",
    "VERDICT_ERROR",
    "AgentDeliberationRecord",
    "GroupDeliberationStats",
    "GroupSliceStats",
    "StatsCalculator",
    "ReliabilityCalculator",
    "PersonaVoter",
    "BaselineResultsWriter",
    "BaselineResultsReader",
    "IndividualVotingRunner",
    "GroupDeliberationRunner",
]
