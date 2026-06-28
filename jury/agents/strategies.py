"""
暗樁策略 (Strategy Pattern) — PlantStrategy 抽象基類。

設計原則：
  此檔案只定義策略介面（PlantStrategy ABC）與裁決方向常數。
  具體策略實作放在獨立檔案中：
    AuthorityStrategy → agents/authority_strategy.py
  未來新增策略時，仿照上述模式建立獨立模組，不修改此檔案。

  隱藏任務 instruction 僅存在於 Agent 的 system prompt 中，
  不會出現在對其他 Agent 可見的 persona 描述裡。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

# 裁決方向常數
VERDICT_GUILTY     = "GUILTY"      # 有罪
VERDICT_NOT_GUILTY = "NOT_GUILTY"  # 無罪


class PlantStrategy(ABC):
    """
    暗樁策略抽象基類 (Abstract Base Class)。

    每個具體策略封裝一種影響手段，透過 get_system_prompt() 回傳
    注入 TinyPerson system prompt 的隱藏任務指令。

    掩護職業與年齡由具體策略各自定義，確保人設一致性。
    """

    @property
    @abstractmethod
    def cover_occupation(self) -> str:
        """掩護職業（Agent 可見的 occupation 欄位）。"""
        ...

    @property
    @abstractmethod
    def cover_age(self) -> int:
        """掩護年齡（Agent 可見的 age 欄位）。"""
        ...

    @abstractmethod
    def get_system_prompt(self, target_verdict: str) -> str:
        """
        產出注入 TinyPerson system prompt 的隱藏任務指令。

        指令必須：
          1. 以英文撰寫（Agent 可見文字）
          2. 詳細到足以讓 Agent 行為穩定、不因細微措辭改變而偏移
          3. 明確包含「不能讓其他人知道你有隱藏任務」的限制
          4. 根據 target_verdict 動態調整推動方向

        Args:
            target_verdict: 推動裁決方向，VERDICT_GUILTY 或 VERDICT_NOT_GUILTY。

        Returns:
            英文隱藏任務指令字串。
        """
        ...
