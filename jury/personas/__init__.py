"""
personas 模組：OCEAN 人格池生成系統。

架構：
  OceanDescriptionPool — LLM 生成 243 個純人格描述
  PersonaPool          — 零 LLM 純組合：描述 × 職業 × Demographic
"""
from personas.factory import PersonaGeneratorFactory
from personas.models import (
    Demographic,
    OceanDescription,
    OceanProfile,
    PersonaProfile,
    ValidationResult,
)
from personas.pool import OceanDescriptionPool, PersonaPool

__all__ = [
    "OceanProfile",
    "OceanDescription",
    "Demographic",
    "PersonaProfile",
    "ValidationResult",
    "PersonaGeneratorFactory",
    "OceanDescriptionPool",
    "PersonaPool",
]
