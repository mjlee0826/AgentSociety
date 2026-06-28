"""
Scenario 資料結構定義。

設計原則：
  Scenario — 單一實驗情境，包含英文完整描述（含封鎖段落）與中文對照。
  所有 Agent 可見的欄位（description_en）必須使用英文，
  description_zh 僅供研究人員閱讀，不傳入 Agent。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# 難度等級常數
DIFFICULTY_HIGH_MORAL_AMBIGUITY = "HIGH_MORAL_AMBIGUITY"
DIFFICULTY_LOW_AMBIGUITY        = "LOW_AMBIGUITY"
DIFFICULTY_FACTUAL_DISPUTE      = "FACTUAL_DISPUTE"

# 基準裁決常數
VERDICT_GUILTY     = "GUILTY"
VERDICT_NOT_GUILTY = "NOT_GUILTY"


@dataclass
class Scenario:
    """
    單一實驗情境的完整定義。

    description_en 是唯一會傳入 Agent 的文字，必須包含：
      1. 完整案件敘述
      2. 法庭確認之絕對事實段落（含「不容置疑」宣告）
      3. 禁止討論主題清單（以自然語言嵌入描述中）
      4. 強制裁決格式指令

    description_zh 僅供研究人員閱讀，不傳入 Agent，避免污染實驗。
    """

    scenario_id: str                          # 唯一識別碼，蛇形命名
    title: str                                # 英文標題
    title_zh: str                             # 中文標題
    description_en: str                       # 完整英文情境描述（Agent 可見）
    description_zh: str                       # 中文對照描述（僅供研究人員）
    difficulty_level: str                     # 難度等級，見上方常數
    expected_baseline_verdict: Optional[str] = None
    # 預期基準裁決（GUILTY / NOT_GUILTY）；非陪審團情境（如煙霧房實驗）設為 None
    # Expected baseline verdict (GUILTY/NOT_GUILTY); None for non-jury scenarios (e.g., smoke room)
    forbidden_discussion_topics: list[str] = field(default_factory=list)
    # 以蛇形命名描述禁止討論的主題鍵，供程式碼邏輯使用

    def to_dict(self) -> dict[str, Any]:
        """序列化為字典，供 JSON / YAML 輸出使用。"""
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "title_zh": self.title_zh,
            "description_en": self.description_en,
            "description_zh": self.description_zh,
            "difficulty_level": self.difficulty_level,
            "expected_baseline_verdict": self.expected_baseline_verdict,
            "forbidden_discussion_topics": self.forbidden_discussion_topics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        """從字典反序列化，用於 YAML 讀取後的建構。"""
        return cls(
            scenario_id=data["scenario_id"],
            title=data["title"],
            title_zh=data["title_zh"],
            description_en=data["description_en"],
            description_zh=data["description_zh"],
            difficulty_level=data["difficulty_level"],
            expected_baseline_verdict=data.get("expected_baseline_verdict"),
            # 非陪審團情境的 YAML 可省略此欄位，預設為 None
            # Non-jury scenarios may omit this field in YAML; defaults to None
            forbidden_discussion_topics=data.get("forbidden_discussion_topics", []),
        )
