"""
experiment/shared/checkpoint.py

泛化斷點續跑管理器。

設計原則：
  CheckpointManager 以 JSONL 格式（每行一個 JSON 物件）逐筆追加已完成的記錄，
  支援 O(1) 追加、O(n) 載入，不需要重寫整個檔案。

  與舊版 checkpoint.py 的關鍵差異：
    - load_records() 改回傳 list[dict]（raw dict），不再硬綁定 VotingRecord。
      型別重建由呼叫端負責（透過 BaseIndividualVotingRunner._record_from_dict()）。
    - append() 接受任何有 .to_dict() 方法的物件（VotingRecord、SmokeDecisionRecord 等）。

  checkpoint key：(persona_id, run_index)，
  讓 reliability 驗證模式（同 persona 多次執行）也能正確續跑。

  檔案命名由呼叫端決定，本類別只負責讀寫，不感知命名規則。
"""
from __future__ import annotations

import json
from pathlib import Path


class CheckpointManager:
    """
    泛化斷點續跑管理器。

    以 JSONL 格式（每行一個 JSON 物件）逐筆追加已完成的決策記錄，
    支援 O(1) 追加、O(n) 載入，不需要重寫整個檔案。

    load_records() 回傳 list[dict]（raw），型別重建由呼叫端負責。
    append() 接受任何有 .to_dict() 的物件。

    checkpoint key：(persona_id, run_index)。

    Args:
        path: checkpoint 檔案的完整路徑。
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def exists(self) -> bool:
        """checkpoint 檔案是否存在。"""
        return self._path.exists()

    def load_done_keys(self) -> set[tuple[str, int]]:
        """
        從 checkpoint 載入已完成的 (persona_id, run_index) 集合。

        舊版 checkpoint 無 run_index 欄位時視為 run_index=0，可向後相容。

        Returns:
            已完成的 (persona_id, run_index) set；檔案不存在則回傳空 set。
        """
        if not self._path.exists():
            return set()
        done: set[tuple[str, int]] = set()
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    done.add((d["persona_id"], d.get("run_index", 0)))
        return done

    def load_records(self) -> list[dict]:
        """
        從 checkpoint 載入所有已完成記錄的 raw dict。

        型別重建由呼叫端負責（如 VotingRecord(**d) 或 SmokeDecisionRecord(**d)）。

        Returns:
            raw dict 列表；檔案不存在則回傳空 list。
        """
        if not self._path.exists():
            return []
        records: list[dict] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def append(self, record) -> None:
        """
        追加一筆完成的記錄到 checkpoint。

        接受任何有 .to_dict() 方法的物件（VotingRecord、SmokeDecisionRecord 等）。
        由主執行緒在 as_completed 迴圈中呼叫，單執行緒寫入，thread-safe。

        Args:
            record: 要追加的記錄物件，需有 .to_dict() 方法。
        """
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def clear(self) -> None:
        """實驗成功完成後刪除 checkpoint 檔案。"""
        if self._path.exists():
            self._path.unlink()
