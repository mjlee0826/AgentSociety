"""
experiment/group_models.py

群體討論實驗的資料結構定義。

設計原則：
  AgentDeliberationRecord — 單一 Agent（正常或暗樁）在群體討論後的最終投票結果。
  GroupSliceStats         — 一個子群（正常 / 暗樁 / 全體）的投票切片統計。
  GroupDeliberationStats  — 整體統計摘要，支援全體 / 正常 / 暗樁三層切片。

此模組只含資料結構，不含任何業務邏輯。
"""
from __future__ import annotations

from dataclasses import dataclass

# ── 統計摘要的浮點數精度
_FLOAT_PRECISION = 4


@dataclass
class AgentDeliberationRecord:
    """
    群體討論後單一 Agent 的最終投票結果。

    正常 Agent：persona_id / ocean_key 有值，strategy_name 為 None。
    暗樁 Agent：persona_id / ocean_key 為 None，strategy_name 有值。

    agent_index 對應 TinyWorld 中 shuffle 後的位置，不代表建立順序。

    Attributes:
        agent_index:   shuffle 後的位置索引（從 0 起算）。
        is_plant:      True 表示暗樁 Agent；False 表示正常 Agent。
        persona_id:    正常 Agent 的 persona 唯一識別碼；暗樁為 None。
        occupation:    正常 Agent 的真實職業；暗樁的掩護職業。
        ocean_key:     OCEAN 五字母縮寫（如 "lmhlh"）；暗樁為 None。
        strategy_name: 暗樁策略名稱（如 "authority"）；正常 Agent 為 None。
        verdict:       "guilty" / "not_guilty" / "parse_error"。
        confidence:    1–10；解析失敗時為 -1。
        reason:        理由段落；解析失敗時為原始回應。
        raw_response:  Agent 的原始 LLM 回應文字。
    """

    agent_index:   int
    is_plant:      bool
    persona_id:    str | None
    occupation:    str
    ocean_key:     str | None
    strategy_name: str | None
    verdict:       str
    confidence:    int
    reason:        str
    raw_response:  str

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "agent_index":   self.agent_index,
            "is_plant":      self.is_plant,
            "persona_id":    self.persona_id,
            "occupation":    self.occupation,
            "ocean_key":     self.ocean_key,
            "strategy_name": self.strategy_name,
            "verdict":       self.verdict,
            "confidence":    self.confidence,
            "reason":        self.reason,
            "raw_response":  self.raw_response,
        }


@dataclass
class GroupSliceStats:
    """
    一個子群（正常 / 暗樁）的投票切片統計。

    不含 guilty_rate / not_guilty_rate（切片樣本小時比率統計意義有限），
    但保留完整計數供後續統計工具使用。

    Attributes:
        total:             子群的 Agent 總數。
        guilty_count:      裁決有罪的數量。
        not_guilty_count:  裁決無罪的數量。
        parse_error_count: 解析失敗的數量。
        dominant_verdict:  多數裁決方向（平局時選 "guilty"）。
    """

    total:             int
    guilty_count:      int
    not_guilty_count:  int
    parse_error_count: int
    dominant_verdict:  str

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "total":             self.total,
            "guilty_count":      self.guilty_count,
            "not_guilty_count":  self.not_guilty_count,
            "parse_error_count": self.parse_error_count,
            "dominant_verdict":  self.dominant_verdict,
        }


@dataclass
class GroupDeliberationStats:
    """
    群體討論實驗的整體投票統計摘要。

    提供三層切片：
      - 全體（含正常 + 暗樁）
      - normal_stats：僅含正常 Agent 的切片
      - plant_stats：僅含暗樁 Agent 的切片

    Attributes:
        total:             所有 Agent 總數。
        guilty_count:      裁決有罪的總數。
        not_guilty_count:  裁決無罪的總數。
        parse_error_count: 解析失敗的總數。
        guilty_rate:       有罪比率（僅計有效票，排除 parse_error）。
        not_guilty_rate:   無罪比率（僅計有效票）。
        dominant_verdict:  全體多數裁決方向（平局時選 "guilty"）。
        normal_stats:      正常 Agent 子群切片統計。
        plant_stats:       暗樁 Agent 子群切片統計。
    """

    total:             int
    guilty_count:      int
    not_guilty_count:  int
    parse_error_count: int
    guilty_rate:       float
    not_guilty_rate:   float
    dominant_verdict:  str
    normal_stats:      GroupSliceStats
    plant_stats:       GroupSliceStats

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。key 為 normal_only / plant_only。"""
        return {
            "total":             self.total,
            "guilty_count":      self.guilty_count,
            "not_guilty_count":  self.not_guilty_count,
            "parse_error_count": self.parse_error_count,
            "guilty_rate":       round(self.guilty_rate, _FLOAT_PRECISION),
            "not_guilty_rate":   round(self.not_guilty_rate, _FLOAT_PRECISION),
            "dominant_verdict":  self.dominant_verdict,
            "normal_only":       self.normal_stats.to_dict(),
            "plant_only":        self.plant_stats.to_dict(),
        }
