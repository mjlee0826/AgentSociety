"""
agents 模組 — 暗樁策略與 Agent 工廠。

公開介面：
  PlantStrategy     — 暗樁策略抽象基類
  AuthorityStrategy — 以退休法官身份發言的具體策略
  AgentFactory      — 統一建立 normal 與 plant agents 的工廠
  VERDICT_GUILTY    — 裁決常數：有罪
  VERDICT_NOT_GUILTY — 裁決常數：無罪
"""

from agents.factory import AgentFactory
from agents.strategies import (
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
    AuthorityStrategy,
    PlantStrategy,
)

__all__ = [
    "PlantStrategy",
    "AuthorityStrategy",
    "AgentFactory",
    "VERDICT_GUILTY",
    "VERDICT_NOT_GUILTY",
]
