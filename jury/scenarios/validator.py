"""
Scenario 驗證器。

確保從 YAML 讀入的 Scenario 包含所有必要欄位且值合法。
驗證失敗時拋出 ScenarioValidationError，附帶具體缺失欄位清單。
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import (
    Scenario,
    DIFFICULTY_HIGH_MORAL_AMBIGUITY,
    DIFFICULTY_LOW_AMBIGUITY,
    DIFFICULTY_FACTUAL_DISPUTE,
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
)

# 允許的難度等級集合
VALID_DIFFICULTY_LEVELS = {
    DIFFICULTY_HIGH_MORAL_AMBIGUITY,
    DIFFICULTY_LOW_AMBIGUITY,
    DIFFICULTY_FACTUAL_DISPUTE,
}

# 允許的基準裁決集合
VALID_BASELINE_VERDICTS = {
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
}

# description_en 必須包含的關鍵段落標記（確保封鎖段落未被遺漏）
REQUIRED_EN_MARKERS = [
    "DELIBERATION CONSTRAINTS",   # 禁止討論主題段落
    "MANDATORY VERDICT FORMAT",   # 強制裁決格式段落
    "ESTABLISHED",                # 絕對事實段落
]


class ScenarioValidationError(Exception):
    """Scenario 驗證失敗時拋出，附帶所有錯誤訊息。"""

    def __init__(self, scenario_id: str, errors: list[str]) -> None:
        self.scenario_id = scenario_id
        self.errors = errors
        bullet_list = "\n  - ".join(errors)
        super().__init__(
            f"Scenario '{scenario_id}' validation failed:\n  - {bullet_list}"
        )


@dataclass
class ScenarioValidationResult:
    """驗證結果，供需要軟性檢查（不拋例外）的情境使用。"""

    is_valid: bool
    errors: list[str]


class ScenarioValidator:
    """
    Scenario 合法性驗證器。

    使用方式：
        validator = ScenarioValidator()
        validator.validate(scenario)          # 失敗時拋出 ScenarioValidationError
        result = validator.check(scenario)    # 失敗時回傳 ScenarioValidationResult
    """

    # 所有必填字串欄位（值不得為空字串）
    # expected_baseline_verdict 不在此列，允許非陪審團情境為 None
    # expected_baseline_verdict is NOT required here — non-jury scenarios may set it to None
    _REQUIRED_STRING_FIELDS = (
        "scenario_id",
        "title",
        "title_zh",
        "description_en",
        "description_zh",
        "difficulty_level",
    )

    def check(self, scenario: Scenario) -> ScenarioValidationResult:
        """軟性驗證，回傳結果物件而非拋出例外。"""
        errors: list[str] = []

        # 必填字串欄位非空檢查
        for field_name in self._REQUIRED_STRING_FIELDS:
            value = getattr(scenario, field_name, None)
            if not value or not str(value).strip():
                errors.append(f"Field '{field_name}' is missing or empty.")

        # 難度等級合法性檢查
        if scenario.difficulty_level and scenario.difficulty_level not in VALID_DIFFICULTY_LEVELS:
            errors.append(
                f"Invalid difficulty_level '{scenario.difficulty_level}'. "
                f"Must be one of: {sorted(VALID_DIFFICULTY_LEVELS)}"
            )

        # 基準裁決合法性檢查（只在有填寫時才驗證）
        # Only validate baseline verdict when it's explicitly set (not None)
        if scenario.expected_baseline_verdict is not None:
            if scenario.expected_baseline_verdict not in VALID_BASELINE_VERDICTS:
                errors.append(
                    f"Invalid expected_baseline_verdict '{scenario.expected_baseline_verdict}'. "
                    f"Must be one of: {sorted(VALID_BASELINE_VERDICTS)} or omitted (None) for non-jury scenarios."
                )

        # forbidden_discussion_topics 必須為 list
        if not isinstance(scenario.forbidden_discussion_topics, list):
            errors.append("Field 'forbidden_discussion_topics' must be a list.")

        # description_en 段落標記檢查：
        #   陪審團情境（expected_baseline_verdict 有值）→ 嚴格要求三個標記
        #   非陪審團情境（expected_baseline_verdict 為 None）→ 跳過陪審團專用標記
        # description_en section marker check:
        #   Jury scenarios (verdict not None) → strictly require all three markers
        #   Non-jury scenarios (verdict is None) → skip jury-specific marker checks
        is_jury_scenario = scenario.expected_baseline_verdict in VALID_BASELINE_VERDICTS
        if is_jury_scenario and scenario.description_en:
            for marker in REQUIRED_EN_MARKERS:
                if marker not in scenario.description_en:
                    errors.append(
                        f"description_en is missing required section marker: '{marker}'. "
                        "Ensure the deliberation constraints, verdict format, and established facts sections are present."
                    )

        return ScenarioValidationResult(is_valid=len(errors) == 0, errors=errors)

    def validate(self, scenario: Scenario) -> None:
        """嚴格驗證，失敗時拋出 ScenarioValidationError。"""
        result = self.check(scenario)
        if not result.is_valid:
            raise ScenarioValidationError(scenario.scenario_id, result.errors)
