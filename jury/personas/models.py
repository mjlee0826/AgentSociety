"""
人物 Persona 資料結構定義。

設計原則：
  OceanDescription  — 243 筆，由 LLM 生成純人格行為描述（不含職業）
  PersonaProfile    — 由 OceanDescription × 職業 × 人口統計純組合而成，無需額外 LLM 呼叫
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

OceanLevel = Literal["low", "medium", "high"]
AgeGroup   = Literal["25-35", "36-50", "51-65"]


@dataclass
class OceanProfile:
    """OCEAN 五大人格維度，每個維度為 low / medium / high。"""

    openness: OceanLevel           # 開放性
    conscientiousness: OceanLevel  # 盡責性
    extraversion: OceanLevel       # 外向性
    agreeableness: OceanLevel      # 親和性
    neuroticism: OceanLevel        # 神經質

    def key(self) -> str:
        """回傳五字母縮寫鍵，用於 de-duplicate（例如 'lmhlh'）。"""
        return "".join(
            v[0]
            for v in (
                self.openness,
                self.conscientiousness,
                self.extraversion,
                self.agreeableness,
                self.neuroticism,
            )
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "openness": self.openness,
            "conscientiousness": self.conscientiousness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "OceanProfile":
        return cls(
            openness=data["openness"],
            conscientiousness=data["conscientiousness"],
            extraversion=data["extraversion"],
            agreeableness=data["agreeableness"],
            neuroticism=data["neuroticism"],
        )


@dataclass
class OceanDescription:
    """
    LLM 生成的純 OCEAN 人格行為描述。
    不含任何職業或人口統計資訊，確保描述可與任意職業組合而不產生混淆。
    """

    ocean: OceanProfile
    description_en: str  # 純人格行為描述（英文），刻意不提職業
    description_zh: str  # description_en 的中文翻譯
    is_valid: bool       # 通過生成 + 驗證則為 True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ocean": self.ocean.to_dict(),
            "description_en": self.description_en,
            "description_zh": self.description_zh,
            "is_valid": self.is_valid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OceanDescription":
        return cls(
            ocean=OceanProfile.from_dict(data["ocean"]),
            description_en=data["description_en"],
            description_zh=data["description_zh"],
            is_valid=data["is_valid"],
        )


@dataclass
class Demographic:
    """人口統計特徵：年齡層與是否有子女。"""

    age_group: AgeGroup  # 年齡層
    is_parent: bool      # 是否為家長

    def to_dict(self) -> dict[str, Any]:
        return {"age_group": self.age_group, "is_parent": self.is_parent}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Demographic":
        return cls(age_group=data["age_group"], is_parent=data["is_parent"])


@dataclass
class PersonaProfile:
    """
    完整的人物 Persona，由 OceanDescription + 職業 + 人口統計純組合而成。
    不需要額外 LLM 呼叫，組合邏輯確保 OCEAN 描述不被職業污染。
    """

    ocean_description: OceanDescription
    occupation: str       # 職業（英文，由 config 指定）
    demographic: Demographic

    @property
    def ocean(self) -> OceanProfile:
        """快捷存取 OCEAN profile。"""
        return self.ocean_description.ocean

    def to_agent_prompt(self) -> str:
        """
        產出 TinyTroupe Agent 可用的 personality 字串。
        純人格描述在前，職業與人口統計背景在後，兩者清楚分離。
        # English: Generates the TinyTroupe personality prompt by appending
        # occupation and demographic context after the OCEAN behavioral description.
        """
        parent_str = "a parent" if self.demographic.is_parent else "not a parent"
        return (
            f"{self.ocean_description.description_en} "
            # 人格描述後接職業與人口統計背景
            f"Professionally, you work as a {self.occupation}. "
            # 職業：由 config 決定，不由 LLM 自行選擇
            f"You are in the {self.demographic.age_group} age group "
            # 年齡層
            f"and are {parent_str}."
            # 是否為家長
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ocean_description": self.ocean_description.to_dict(),
            "occupation": self.occupation,
            "demographic": self.demographic.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonaProfile":
        return cls(
            ocean_description=OceanDescription.from_dict(data["ocean_description"]),
            occupation=data["occupation"],
            demographic=Demographic.from_dict(data["demographic"]),
        )


@dataclass
class ValidationResult:
    """
    LLM 驗證結果。
    reason 在 is_valid=False 時說明失敗原因，供重新生成時注入 prompt。
    """

    is_valid: bool
    reason: str = ""  # 失敗原因；通過時為空字串
