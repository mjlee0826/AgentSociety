"""
experiment/shared 子套件 — jury 與 bystander 實驗共用基礎設施。

公開介面：
  DecisionSchema         — 決策格式規格
  JURY_SCHEMA            — 陪審團 schema（VERDICT: guilty/not_guilty）
  BYSTANDER_SCHEMA       — 旁觀者 schema（ACTION: report/wait/ignore）
  ResponseParser         — Agent 回應解析器
  GenericDecisionVoter   — 泛化個人決策 Agent 執行器
  BaseStatsCalculator    — 共用統計計算基類
  BaseReliabilityCalculator — 共用可靠性計算基類
  PersonaReliabilityBase — domain-neutral persona reliability 指標
  ReliabilityStatsBase   — domain-neutral reliability 整體摘要
  BaseIndividualVotingRunner — 個人決策實驗 Template Method 基類
  CheckpointManager      — 泛化斷點續跑管理器
  PersonaLoader          — Persona 池載入器
  PersonaSampler         — Persona 子集選擇器
  OccupationCategoryMapper — 職業 → 類別映射器
  build_persona_id       — Persona 唯一識別碼產生函式
"""

from experiment.shared.schemas import DecisionSchema, JURY_SCHEMA, BYSTANDER_SCHEMA
from experiment.shared.parser import ResponseParser
from experiment.shared.decision_voter import GenericDecisionVoter
from experiment.shared.stats import BaseStatsCalculator
from experiment.shared.reliability import (
    BaseReliabilityCalculator,
    PersonaReliabilityBase,
    ReliabilityStatsBase,
)
from experiment.shared.individual_voting import BaseIndividualVotingRunner
from experiment.shared.checkpoint import CheckpointManager
from experiment.shared.loader import PersonaLoader
from experiment.shared.sampler import PersonaSampler
from experiment.shared.mappers import OccupationCategoryMapper
from experiment.shared.utils import build_persona_id

__all__ = [
    "DecisionSchema",
    "JURY_SCHEMA",
    "BYSTANDER_SCHEMA",
    "ResponseParser",
    "GenericDecisionVoter",
    "BaseStatsCalculator",
    "BaseReliabilityCalculator",
    "PersonaReliabilityBase",
    "ReliabilityStatsBase",
    "BaseIndividualVotingRunner",
    "CheckpointManager",
    "PersonaLoader",
    "PersonaSampler",
    "OccupationCategoryMapper",
    "build_persona_id",
]
