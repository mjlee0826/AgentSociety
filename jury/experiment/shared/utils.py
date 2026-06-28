"""
experiment/shared/utils.py

實驗模組共用工具函式。

設計原則：
  此模組只放純工具函式（無 I/O、無 LLM 呼叫），
  確保可被多個實驗模組（voter、sampler、checkpoint 等）安全共用。

  jury / bystander 兩個子套件均可直接引用，無需各自維護。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from personas.models import PersonaProfile


def build_persona_id(persona: PersonaProfile) -> str:
    """
    為 PersonaProfile 產出唯一識別碼。

    格式：{ocean_key}_{occupation_slug}_{age_group}_{is_parent_int}
    例如：lmhlh_defense_attorney_36-50_1

    Args:
        persona: 要產出 ID 的 PersonaProfile。

    Returns:
        唯一識別碼字串。
    """
    occ_slug  = persona.occupation.replace(" ", "_")
    is_parent = int(persona.demographic.is_parent)
    age_group = persona.demographic.age_group
    return f"{persona.ocean.key()}_{occ_slug}_{age_group}_{is_parent}"
