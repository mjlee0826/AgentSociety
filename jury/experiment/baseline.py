"""
experiment/baseline.py

Baseline 裁決結果的持久化器。

將 dominant_verdict 寫入 config/baseline_results.json，
供後續暗樁實驗讀取，以決定「推動方向的逆流目標」。

JSON 結構：
  {
    "{scenario_id}": {
      "dominant_verdict": "not_guilty",
      "timestamp": "2026-05-13T03:00:00",
      "total_valid_votes": 100,
      "guilty_count": 30,
      "not_guilty_count": 70
    }
  }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from experiment.models import VotingStats

# 預設 baseline 結果路徑
_DEFAULT_PATH = Path(__file__).parent.parent / "config" / "baseline_results.json"


class BaselineResultsWriter:
    """
    以 scenario_id 為 key 更新 baseline_results.json。

    若檔案已存在則合併（不覆蓋其他 scenario 的記錄），
    確保多個 scenario 的 baseline 可以共存於同一個 JSON 檔案中。

    Args:
        path: baseline_results.json 的寫入路徑；預設為 config/baseline_results.json。
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path

    def write(self, scenario_id: str, stats: "VotingStats", timestamp: str) -> None:
        """
        將指定 scenario 的 dominant_verdict 與統計數字寫入 JSON。

        Args:
            scenario_id: Scenario 的唯一識別碼（用作 JSON key）。
            stats:       本次實驗的統計結果。
            timestamp:   本次實驗的時間戳記（ISO 格式字串）。
        """
        # 讀取現有內容（若存在）
        # Load existing content if present
        existing: dict = {}
        if self._path.exists():
            with self._path.open("r", encoding="utf-8") as f:
                existing = json.load(f)

        # 更新指定 scenario 的記錄
        # Update the entry for this scenario
        existing[scenario_id] = {
            "dominant_verdict": stats.dominant_verdict,
            "timestamp": timestamp,
            "total_valid_votes": stats.guilty_count + stats.not_guilty_count,
            "guilty_count": stats.guilty_count,
            "not_guilty_count": stats.not_guilty_count,
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
