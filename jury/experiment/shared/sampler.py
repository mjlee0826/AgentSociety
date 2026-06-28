"""
experiment/shared/sampler.py

Persona 子集選擇器。

設計原則：
  PersonaSampler 只負責「從完整 persona 池中選出子集」，
  不負責載入、不負責投票，職責單一。

  支援兩種互斥的選擇模式：
    - 隨機抽樣 (sample_size + seed)：可重現的均勻隨機抽樣
    - 指定 ID 清單 (persona_ids_file)：讀取文字檔，一行一個 persona_id

  若兩種模式都未指定，回傳全部 personas（baseline 模式）。

  jury / bystander 兩個子套件均可直接引用，無需各自維護。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from personas.models import PersonaProfile
from experiment.shared.utils import build_persona_id


class PersonaSampler:
    """
    Persona 子集選擇器。

    用於 reliability 驗證實驗，從完整 persona 池抽出較小的子集進行重複測量。
    支援兩種互斥的選擇模式：
      - 隨機抽樣 (sample_size + seed)：可重現的均勻隨機抽樣
      - 指定 ID 清單 (persona_ids_file)：讀取文字檔，一行一個 persona_id

    若兩種模式都未指定，回傳全部 personas（baseline 模式）。
    """

    def select(
        self,
        personas: list[PersonaProfile],
        sample_size: int | None,
        seed: int,
        persona_ids_file: Path | None,
    ) -> list[PersonaProfile]:
        """
        依參數選擇 persona 子集。

        Args:
            personas:         完整 persona 池（已過濾 is_valid=True）。
            sample_size:      若提供，隨機抽樣此數量。
            seed:             隨機抽樣 RNG seed，確保可重現。
            persona_ids_file: 若提供，讀取此檔案內列出的 persona_id；
                              優先順序高於 sample_size。

        Returns:
            選出的 PersonaProfile 列表。
        """
        if persona_ids_file is not None:
            wanted   = self._load_persona_ids(persona_ids_file)
            selected = [p for p in personas if build_persona_id(p) in wanted]
            missing  = wanted - {build_persona_id(p) for p in selected}
            if missing:
                # 提示使用者哪些 ID 在 pool 中找不到，協助排查 typo
                # Warn about IDs not found in the pool (typo check)
                print(f"Warning: {len(missing)} persona_id(s) in file not found in pool.")
                for m in sorted(missing)[:5]:
                    print(f"  - {m}")
                if len(missing) > 5:
                    print(f"  ... and {len(missing) - 5} more.")
            return selected

        if sample_size is not None:
            rng = random.Random(seed)
            # 不超出 pool 大小，避免 ValueError
            # Cap at pool size to avoid ValueError
            return rng.sample(personas, min(sample_size, len(personas)))

        return personas

    def _load_persona_ids(self, path: Path) -> set[str]:
        """從文字檔載入 persona_id 集合（一行一個，忽略空行與 # 註解）。"""
        if not path.exists():
            raise FileNotFoundError(f"persona_ids_file not found: {path}")
        ids: set[str] = set()
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ids.add(line)
        return ids
