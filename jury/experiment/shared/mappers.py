"""
experiment/shared/mappers.py

實驗模組共用映射工具。

設計原則：
  OccupationCategoryMapper — 從 personas.yaml 動態建立職業 → 類別映射，
  避免在程式碼中硬寫職業清單，確保職業擴充時不需修改程式碼。

  jury / bystander 兩個子套件均可直接引用，無需各自維護。
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

# 預設 YAML 路徑
# Default YAML path
_PERSONAS_YAML = _JURY_ROOT / "config" / "personas.yaml"


class OccupationCategoryMapper:
    """
    從 personas.yaml 建立職業 → 類別的映射表，避免硬寫職業清單。

    Args:
        yaml_path: personas.yaml 路徑；預設為 config/personas.yaml。
    """

    def __init__(self, yaml_path: Path = _PERSONAS_YAML) -> None:
        self._mapping: dict[str, str] = {}
        self._load(yaml_path)

    def _load(self, yaml_path: Path) -> None:
        """從 YAML 讀取職業類別，建立 occupation → category 映射。"""
        if not yaml_path.exists():
            return
        with yaml_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        for category, occupations in config.get("occupations", {}).items():
            for occ in occupations:
                self._mapping[occ] = category

    def get_category(self, occupation: str) -> str:
        """
        回傳職業所屬類別；若找不到則回傳 'unknown'。

        Args:
            occupation: 職業字串（須與 personas.yaml 完全一致）。
        """
        return self._mapping.get(occupation, "unknown")
