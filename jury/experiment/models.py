"""
experiment/models.py

個人投票實驗的資料結構定義。

設計原則：
  VotingRecord — 單一 Persona 的投票結果，包含完整的人口統計與 OCEAN 資訊。
  VotingStats  — 整體統計摘要，供 JSON 輸出與 baseline 寫入使用。
"""
from __future__ import annotations

from dataclasses import dataclass

# ── 裁決常數（小寫，與 scenarios.models 的 GUILTY / NOT_GUILTY 大寫常數分離）
# Verdict constants (lowercase, separate from scenarios.models uppercase constants)
VERDICT_GUILTY     = "guilty"       # 有罪
VERDICT_NOT_GUILTY = "not_guilty"   # 無罪
VERDICT_ERROR      = "parse_error"  # Agent 回應解析失敗


@dataclass
class VotingRecord:
    """
    單一 Persona 的個人投票結果。

    persona_id 格式：{ocean_key}_{occupation_slug}_{age_group}_{is_parent_int}
    例如：lmhlh_defense_attorney_36-50_1
    """

    persona_id: str             # 唯一識別碼
    ocean_profile: dict         # OceanProfile.to_dict()
    ocean_key: str              # 五字母縮寫，如 'lmhlh'
    occupation: str             # 職業原始字串
    occupation_category: str    # 職業類別，如 'legal' / 'medical'
    demographic: dict           # Demographic.to_dict()
    verdict: str                # 'guilty' / 'not_guilty' / 'parse_error'
    confidence: int             # 1–10；解析失敗時為 -1
    reason: str                 # 理由段落；解析失敗時為原始回應
    raw_response: str           # Agent 的原始回應文字

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "persona_id": self.persona_id,
            "ocean_profile": self.ocean_profile,
            "ocean_key": self.ocean_key,
            "occupation": self.occupation,
            "occupation_category": self.occupation_category,
            "demographic": self.demographic,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "reason": self.reason,
            "raw_response": self.raw_response,
        }


@dataclass
class VotingStats:
    """
    整體投票統計摘要。

    by_occupation_category 結構：
      { category: { guilty_count, not_guilty_count, total, guilty_rate, not_guilty_rate } }

    by_ocean_dimension 結構：
      { dimension: { high: { count, guilty_count, ... }, low: { ... } } }
    """

    total: int
    guilty_count: int
    not_guilty_count: int
    parse_error_count: int
    guilty_rate: float
    not_guilty_rate: float
    dominant_verdict: str        # 多數裁決方向
    by_occupation_category: dict # 各職業類別投票分佈
    by_ocean_dimension: dict     # 各 OCEAN 維度高低對投票傾向的影響

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "total": self.total,
            "guilty_count": self.guilty_count,
            "not_guilty_count": self.not_guilty_count,
            "parse_error_count": self.parse_error_count,
            "guilty_rate": round(self.guilty_rate, 4),
            "not_guilty_rate": round(self.not_guilty_rate, 4),
            "dominant_verdict": self.dominant_verdict,
            "by_occupation_category": self.by_occupation_category,
            "by_ocean_dimension": self.by_ocean_dimension,
        }
