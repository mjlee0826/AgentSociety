"""
scenarios 模組公開 API。

使用方式：
    from jury.scenarios import ScenarioLoader, Scenario, ScenarioValidator
    loader   = ScenarioLoader()
    scenario = loader.load_by_id("father_theft_medicine")
"""

from .loader import ScenarioLoader, ScenarioNotFoundError
from .models import (
    Scenario,
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
    DIFFICULTY_HIGH_MORAL_AMBIGUITY,
    DIFFICULTY_LOW_AMBIGUITY,
    DIFFICULTY_FACTUAL_DISPUTE,
)
from .validator import ScenarioValidator, ScenarioValidationError, ScenarioValidationResult

__all__ = [
    "Scenario",
    "ScenarioLoader",
    "ScenarioNotFoundError",
    "ScenarioValidator",
    "ScenarioValidationError",
    "ScenarioValidationResult",
    "VERDICT_GUILTY",
    "VERDICT_NOT_GUILTY",
    "DIFFICULTY_HIGH_MORAL_AMBIGUITY",
    "DIFFICULTY_LOW_AMBIGUITY",
    "DIFFICULTY_FACTUAL_DISPUTE",
]
