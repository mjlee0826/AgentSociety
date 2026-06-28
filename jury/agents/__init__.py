"""
agents 模組 — 暗樁策略與 Agent 工廠。

公開介面：
  PlantStrategy              — 暗樁策略抽象基類
  AuthorityStrategy          — 以退休法官身份發言的具體策略（陪審團實驗）
  ConfederateIgnoreStrategy  — 以普通受試者身份淡化煙霧的具體策略（旁觀者實驗）
  AgentFactory               — 統一建立 normal 與 plant agents 的工廠
  VERDICT_GUILTY             — 裁決常數：有罪
  VERDICT_NOT_GUILTY         — 裁決常數：無罪
"""

from agents.authority_strategy import AuthorityStrategy
from agents.confederate_strategy import ConfederateIgnoreStrategy
from agents.factory import AgentFactory
from agents.strategies import (
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
    PlantStrategy,
)

__all__ = [
    "PlantStrategy",
    "AuthorityStrategy",
    "ConfederateIgnoreStrategy",
    "AgentFactory",
    "VERDICT_GUILTY",
    "VERDICT_NOT_GUILTY",
]
