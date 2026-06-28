"""
experiment/shared/loader.py

Persona 池載入器。

設計原則：
  PersonaLoader 只負責讀取 JSON 並過濾 is_valid=True 的記錄，
  不負責任何 LLM 呼叫或 sampling 邏輯，職責單一。

  jury / bystander 兩個實驗子套件均可直接使用此模組，無需各自維護。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from personas.models import PersonaProfile


class PersonaLoader:
    """
    從 JSON 載入並過濾 PersonaProfile 的包裝器。

    只回傳 ocean_description.is_valid == True 的 Persona，
    確保即使 JSON 中混有無效記錄也能安全處理。
    """

    def load(self, path: Path) -> list[PersonaProfile]:
        """
        載入 persona pool JSON，回傳所有 is_valid=True 的 PersonaProfile。

        Args:
            path: persona pool JSON 路徑（通常為 personas_output.json）。

        Returns:
            PersonaProfile 列表，只含 is_valid=True 的記錄。

        Raises:
            FileNotFoundError: JSON 檔案不存在時拋出。
        """
        if not path.exists():
            raise FileNotFoundError(
                f"Persona pool JSON not found at: {path}. "
                "Please run generate_personas.py first."
            )
        with path.open("r", encoding="utf-8") as f:
            raw: list[dict] = json.load(f)

        # 過濾 is_valid=True 的記錄
        # Filter records where ocean_description.is_valid is True
        return [
            PersonaProfile.from_dict(d)
            for d in raw
            if d.get("ocean_description", {}).get("is_valid", False)
        ]
