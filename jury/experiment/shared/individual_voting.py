"""
experiment/shared/individual_voting.py

個人決策實驗共用 Template Method 基類。

設計原則：
  BaseIndividualVotingRunner 定義「個人決策實驗」的固定流程骨架（run()），
  由 jury/individual_voting.py（IndividualVotingRunner）與
  bystander/individual_voting.py（SmokeIndividualVotingRunner）各自繼承。

  子類別只需實作 abstract hooks，不需重寫整個執行流程。

  固定流程（由 run() 強制執行）：
    1. 載入 Persona 池
    2. PersonaSampler 抽樣
    3. 載入 Scenario
    4. 建立 voter（hook）
    5. 初始化 CheckpointManager
    6. ThreadPoolExecutor 並行投票（支援斷點續跑）
    7. 計算統計摘要（hook）
    8. 可選：計算 reliability 摘要（hook，repeat > 1 時）
    9. 輸出 JSON（hook）
   10. Post-run hook（如更新 baseline，預設 no-op）
   11. 清除 checkpoint

  子類別 abstract hooks：
    _create_voter(scenario, category_mapper, parser)
    _make_error_record(persona, run_idx, error_msg)
    _record_from_dict(d)                    ← checkpoint 重建
    _compute_stats(records)
    _compute_reliability(records, repeat_n) ← 可回傳 None
    _agent_name_for(i, persona, run_idx)
    _build_output(records, stats, scenario, timestamp, reliability_stats)
    _output_filename(scenario, timestamp)

  可選 hook（有預設行為）：
    _after_run(records, stats, scenario_id, timestamp)  ← 預設 no-op
    _checkpoint_suffix()                                ← 預設 ""
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import json

from tqdm import tqdm

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from personas.models import PersonaProfile
from scenarios.loader import ScenarioLoader

from experiment.shared.checkpoint import CheckpointManager
from experiment.shared.loader import PersonaLoader
from experiment.shared.mappers import OccupationCategoryMapper
from experiment.shared.parser import ResponseParser
from experiment.shared.reliability import ReliabilityStatsBase
from experiment.shared.sampler import PersonaSampler
from experiment.shared.utils import build_persona_id

# ── 預設路徑
_DEFAULT_PERSONA_POOL = _JURY_ROOT / "personas_output.json"
_DEFAULT_OUTPUT_DIR   = _JURY_ROOT / "results"

# 預設並發執行緒數
# Default worker count
_DEFAULT_MAX_WORKERS = 4

# 預設抽樣 RNG seed
# Default RNG seed for reproducible sampling
_DEFAULT_SAMPLE_SEED = 42

# 預設重複次數（1 = 普通 baseline；>1 = reliability 驗證模式）
# Default repeat count (1 = baseline; >1 = reliability validation)
_DEFAULT_REPEAT = 1


class BaseIndividualVotingRunner(ABC):
    """
    個人決策實驗的 Template Method 基類。

    run() 定義固定流程骨架，子類別實作 domain-specific hooks。

    支援兩種模式（由 repeat 參數切換）：
      - repeat=1：標準 baseline，每 persona 決策一次
      - repeat>1：reliability 驗證，每 persona 決策 N 次，計算 modal agreement

    Args:
        scenario_id:       要執行的 Scenario ID。
        persona_pool_path: persona pool JSON 的路徑。
        output_dir:        結果 JSON 的輸出目錄。
        max_workers:       並發執行緒數。
        limit:             只跑前 N 個 persona（煙霧測試用）。
        repeat:            每 persona 的重複測量次數，預設 1。
        sample_size:       隨機抽樣的 persona 數；None = 全部。
        sample_seed:       抽樣 RNG seed。
        persona_ids_file:  指定 persona_id 清單檔；優先於 sample_size。
    """

    def __init__(
        self,
        scenario_id: str,
        persona_pool_path: Path = _DEFAULT_PERSONA_POOL,
        output_dir: Path = _DEFAULT_OUTPUT_DIR,
        max_workers: int = _DEFAULT_MAX_WORKERS,
        limit: int | None = None,
        repeat: int = _DEFAULT_REPEAT,
        sample_size: int | None = None,
        sample_seed: int = _DEFAULT_SAMPLE_SEED,
        persona_ids_file: Path | None = None,
    ) -> None:
        if repeat < 1:
            raise ValueError(f"repeat must be >= 1, got {repeat}")

        self._scenario_id       = scenario_id
        self._persona_pool_path = persona_pool_path
        self._output_dir        = output_dir
        self._max_workers       = max_workers
        # None = 跑全部；正整數 = 只跑前 N 個（煙霧測試用）
        # None = run all; positive int = run only first N (smoke test)
        self._limit             = limit
        self._repeat            = repeat
        self._sample_size       = sample_size
        self._sample_seed       = sample_seed
        self._persona_ids_file  = persona_ids_file

        # 共用依賴組件（子類別可覆寫）
        self._persona_loader  = PersonaLoader()
        self._persona_sampler = PersonaSampler()
        self._category_mapper = OccupationCategoryMapper()

    @property
    def _is_reliability_mode(self) -> bool:
        """repeat > 1 視為 reliability 驗證模式。"""
        return self._repeat > 1

    # ─────────────────────────────────────────────────────────────────────
    #  Template Method（固定流程骨架，不覆寫）
    # ─────────────────────────────────────────────────────────────────────

    def run(self) -> Path:
        """
        執行完整的個人決策實驗。

        固定流程，不覆寫。子類別透過 abstract hooks 注入 domain-specific 行為。

        Returns:
            輸出 JSON 檔案的路徑。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. 載入 Persona 池
        print(f"Loading persona pool from: {self._persona_pool_path}")
        personas = self._persona_loader.load(self._persona_pool_path)
        print(f"Loaded {len(personas)} valid personas from pool.")

        # 2. 抽樣（隨機 / 指定清單 / 全部）
        # Sub-sample (random / id-list / all)
        personas = self._persona_sampler.select(
            personas,
            sample_size=self._sample_size,
            seed=self._sample_seed,
            persona_ids_file=self._persona_ids_file,
        )
        if self._limit is not None:
            personas = personas[: self._limit]
        print(f"Running on {len(personas)} persona(s) x {self._repeat} run(s) "
              f"= {len(personas) * self._repeat} total LLM call(s).")

        if not personas:
            raise RuntimeError("No personas selected for this experiment. Check sampling args.")

        # 3. 載入 Scenario
        loader   = ScenarioLoader()
        scenario = loader.load_by_id(self._scenario_id)
        print(f"Scenario loaded: [{scenario.scenario_id}] {scenario.title}")

        # 4. 建立 voter（domain-specific hook）
        parser = ResponseParser(self._schema)
        voter  = self._create_voter(scenario, self._category_mapper, parser)

        # 5. 初始化 checkpoint
        self._output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self._build_checkpoint_path()
        checkpoint      = CheckpointManager(checkpoint_path)
        if checkpoint.exists:
            print(f"Found checkpoint: {checkpoint_path}")
            print(f"  To reset and start over, delete the checkpoint file.")

        # 6. 並行執行（支援斷點續跑）
        print(f"Starting parallel voting with {self._max_workers} workers...")
        records = self._run_voting_parallel(voter, personas, checkpoint)

        # 7. 計算統計摘要
        stats = self._compute_stats(records)

        # 8. reliability 模式：額外計算 modal agreement
        reliability_stats = None
        if self._is_reliability_mode:
            reliability_stats = self._compute_reliability(records, self._repeat)
            if reliability_stats is not None:
                self._print_reliability_summary(reliability_stats)

        # 9. 輸出結果 JSON
        output_path = self._write_output(
            records, stats, scenario, timestamp, reliability_stats
        )
        print(f"\nResults written to: {output_path}")

        # 10. Post-run hook（jury 更新 baseline；bystander 預設 no-op）
        self._after_run(records, stats, self._scenario_id, timestamp)

        # 11. 清除 checkpoint
        checkpoint.clear()

        return output_path

    # ─────────────────────────────────────────────────────────────────────
    #  共用具體方法（通常不需要覆寫）
    # ─────────────────────────────────────────────────────────────────────

    def _run_voting_parallel(
        self,
        voter,
        personas: list[PersonaProfile],
        checkpoint: CheckpointManager,
    ) -> list:
        """
        以 ThreadPoolExecutor 並行執行所有 (persona, run_index) 任務，支援斷點續跑。

        reliability 模式下，同一 persona 會被排入 repeat 次任務，每次具有不同
        run_index 與不同 agent_name；voter.vote() 每次都建立全新 TinyPerson，
        確保 LLM 呼叫間沒有狀態殘留。
        每筆完成後立即寫入 checkpoint；若個別執行緒拋出例外，
        該 (persona, run_index) 的結果被記錄為 error record，不影響其他執行緒。

        Args:
            voter:      voter 實例（唯讀共用，thread-safe）。
            personas:   待決策的 PersonaProfile 列表。
            checkpoint: CheckpointManager 實例。

        Returns:
            全部決策記錄列表（已完成 + 本次新完成）。
        """
        # 從 checkpoint 載入已完成的 (persona_id, run_index) 集合
        # Load completed (persona_id, run_index) keys from checkpoint
        done_keys = checkpoint.load_done_keys()
        # checkpoint 回傳 raw dict，由 _record_from_dict 重建
        # Checkpoint returns raw dicts; _record_from_dict() reconstructs typed records
        completed_records = [
            self._record_from_dict(d) for d in checkpoint.load_records()
        ]

        # 展開成全部任務，過濾已完成
        # Expand into (persona, run_index) tasks, skip done
        all_tasks: list[tuple[PersonaProfile, int]] = [
            (p, r)
            for p in personas
            for r in range(self._repeat)
        ]
        remaining_tasks = [
            (p, r) for p, r in all_tasks
            if (build_persona_id(p), r) not in done_keys
        ]

        if done_keys:
            print(f"Resuming: {len(done_keys)} task(s) already done, "
                  f"{len(remaining_tasks)} remaining.")

        new_records: list = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_task = {
                executor.submit(
                    voter.vote,
                    persona,
                    self._agent_name_for(i, persona, run_idx),
                    run_idx,
                ): (persona, run_idx)
                for i, (persona, run_idx) in enumerate(remaining_tasks)
            }
            with tqdm(
                total=len(all_tasks),
                initial=len(done_keys),
                desc="Individual voting",
                unit="run",
            ) as pbar:
                for future in as_completed(future_to_task):
                    persona, run_idx = future_to_task[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        # 單一執行緒失敗不中斷整體實驗，記錄為 error
                        # Single thread failure doesn't abort the experiment
                        record = self._make_error_record(persona, run_idx, repr(exc))
                    # 主執行緒寫入 checkpoint，single-threaded，thread-safe
                    checkpoint.append(record)
                    new_records.append(record)
                    pbar.update(1)

        return completed_records + new_records

    def _build_checkpoint_path(self) -> Path:
        """
        依模式產生 checkpoint 路徑。

        reliability 模式加上 _reliability_r{N} 後綴，
        避免與 baseline checkpoint 互相覆蓋。
        """
        suffix = self._checkpoint_suffix()
        if self._is_reliability_mode:
            return self._output_dir / (
                f".checkpoint_{self._scenario_id}{suffix}_reliability_r{self._repeat}.jsonl"
            )
        return self._output_dir / f".checkpoint_{self._scenario_id}{suffix}.jsonl"

    def _print_reliability_summary(self, rel: ReliabilityStatsBase) -> None:
        """在終端機印出簡明的 reliability 摘要供使用者快速判讀。"""
        print("\n── Reliability summary ─────────────────────────────")
        print(f"  Personas tested        : {rel.total_personas}")
        print(f"  Runs per persona       : {rel.repeat_n}")
        print(f"  Mean modal agreement   : {rel.mean_modal_agreement:.4f}")
        print(f"  Min  modal agreement   : {rel.min_modal_agreement:.4f}")
        print(f"  Fully consistent rate  : {rel.fully_consistent_rate:.4f} "
              f"({rel.fully_consistent_count}/{rel.total_personas})")
        print(f"  Mean confidence SD     : {rel.mean_confidence_sd:.4f}")
        print(f"  Modal agreement buckets:")
        for bucket, count in rel.modal_agreement_buckets.items():
            print(f"    {bucket:>14s} : {count}")
        print("───────────────────────────────────────────────────")

    def _write_output(
        self,
        records: list,
        stats,
        scenario,
        timestamp: str,
        reliability_stats=None,
    ) -> Path:
        """
        將決策記錄與統計摘要寫入 JSON 輸出檔案。

        Args:
            records:           所有決策記錄。
            stats:             統計摘要。
            scenario:          執行實驗的 Scenario。
            timestamp:         時間戳記字串（YYYYMMDD_HHMMSS）。
            reliability_stats: ReliabilityStatsBase；reliability 模式才有。

        Returns:
            輸出檔案路徑。
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename    = self._output_filename(scenario, timestamp)
        output_path = self._output_dir / filename

        # 計算 unique persona 數（reliability 下 unique < total）
        unique_personas = len({r.persona_id for r in records})

        output = self._build_output(records, stats, scenario, timestamp, reliability_stats)
        # 確保 metadata 中包含共用欄位
        # Ensure metadata contains common fields
        output.setdefault("metadata", {})
        output["metadata"].update({
            "unique_personas":   unique_personas,
            "total_records":     len(records),
            "mode":              "reliability" if self._is_reliability_mode else "baseline",
            "repeat":            self._repeat,
            "sample_size":       self._sample_size,
            "sample_seed":       self._sample_seed,
            "persona_ids_file":  str(self._persona_ids_file) if self._persona_ids_file else None,
            "persona_pool_path": str(self._persona_pool_path),
        })

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return output_path

    # ─────────────────────────────────────────────────────────────────────
    #  可選 hook（有預設行為，子類別可覆寫）
    # ─────────────────────────────────────────────────────────────────────

    def _after_run(self, records, stats, scenario_id: str, timestamp: str) -> None:
        """
        Post-run hook（例如更新 baseline_results.json）。

        預設 no-op；jury 子類別覆寫以呼叫 BaselineResultsWriter。
        reliability 模式下即使 jury 也不更新 baseline（避免污染）。
        """
        pass  # bystander 無需更新 baseline

    def _checkpoint_suffix(self) -> str:
        """
        checkpoint 檔名後綴（區分 jury / bystander 避免命名衝突）。

        預設 ""；子類別可覆寫（如 "_smoke"）。
        """
        return ""

    # ─────────────────────────────────────────────────────────────────────
    #  Abstract hooks（子類別必須實作）
    # ─────────────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def _schema(self):
        """
        DecisionSchema 實例（JURY_SCHEMA 或 BYSTANDER_SCHEMA）。

        用於建立 ResponseParser 與傳遞給 BaseReliabilityCalculator.calculate()。
        """

    @abstractmethod
    def _create_voter(self, scenario, category_mapper, parser):
        """
        建立 domain-specific voter 實例。

        Args:
            scenario:        Scenario 實例。
            category_mapper: OccupationCategoryMapper 實例。
            parser:          ResponseParser 實例（已用 schema 初始化）。

        Returns:
            voter 實例（有 vote(persona, agent_name, run_index) 方法）。
        """

    @abstractmethod
    def _make_error_record(self, persona: PersonaProfile, run_idx: int, error_msg: str):
        """
        執行緒發生未預期例外時，建立 error record。

        Args:
            persona:   發生例外的 PersonaProfile。
            run_idx:   重複測量編號。
            error_msg: 例外訊息字串。

        Returns:
            verdict/decision=error_value 的 domain-specific record。
        """

    @abstractmethod
    def _record_from_dict(self, d: dict):
        """
        從 checkpoint 的 raw dict 重建 domain-specific record。

        Args:
            d: checkpoint 中的 raw JSON dict。

        Returns:
            domain-specific record 物件（如 VotingRecord 或 SmokeDecisionRecord）。
        """

    @abstractmethod
    def _compute_stats(self, records: list):
        """
        計算統計摘要。

        Args:
            records: 所有決策記錄。

        Returns:
            domain-specific 統計摘要物件（如 VotingStats 或 SmokeDecisionStats）。
        """

    @abstractmethod
    def _compute_reliability(self, records: list, repeat_n: int):
        """
        計算 reliability 摘要（reliability 模式下呼叫）。

        Args:
            records:   含多個 run_index 的所有決策記錄。
            repeat_n:  設計上每 persona 的重複次數。

        Returns:
            ReliabilityStatsBase 物件；若不支援則回傳 None。
        """

    @abstractmethod
    def _agent_name_for(self, i: int, persona: PersonaProfile, run_idx: int) -> str:
        """
        為 (persona, run_index) 任務產出唯一的 TinyPerson agent_name。

        Args:
            i:       任務在 remaining_tasks 列表中的索引（確保唯一性）。
            persona: 要命名的 PersonaProfile。
            run_idx: 重複測量編號。

        Returns:
            唯一 agent_name 字串。
        """

    @abstractmethod
    def _build_output(
        self,
        records: list,
        stats,
        scenario,
        timestamp: str,
        reliability_stats,
    ) -> dict:
        """
        建立 JSON 輸出的 dict 結構。

        _write_output() 會自動補上共用的 metadata 欄位，
        此 hook 只需提供 domain-specific 部分（包含 metadata 的 domain 欄位）。

        Args:
            records:           所有決策記錄。
            stats:             統計摘要。
            scenario:          Scenario 實例。
            timestamp:         時間戳記字串。
            reliability_stats: ReliabilityStatsBase 或 None。

        Returns:
            JSON-serializable dict。
        """

    @abstractmethod
    def _output_filename(self, scenario, timestamp: str) -> str:
        """
        產出 JSON 輸出檔名（含副檔名）。

        Args:
            scenario:  Scenario 實例。
            timestamp: 時間戳記字串（YYYYMMDD_HHMMSS）。

        Returns:
            檔名字串（不含路徑）。
        """
