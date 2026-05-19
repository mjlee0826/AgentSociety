"""
Phase 2 執行入口：個人投票實驗（無群體討論）。

每個 is_valid=True 的 Persona 單獨面對指定 Scenario，
記錄其個人 VERDICT / CONFIDENCE / REASON，
並輸出統計摘要與 baseline_results.json 供後續暗樁實驗使用。

支援 reliability 驗證模式：以 --repeat N 讓每個 Persona 重複投票 N 次，
搭配 --sample_size 或 --persona_ids_file 抽樣子集，用於量化 LLM
stochasticity 對個人裁決的污染（modal agreement rate / confidence SD）。

用法（baseline）：
  cd jury
  python experiment/individual_voting.py
  python experiment/individual_voting.py --scenario_id father_theft_medicine
  python experiment/individual_voting.py --max_workers 8
  python experiment/individual_voting.py --limit 5          # 煙霧測試

用法（reliability 驗證）：
  # 隨機抽 48 人，每人跑 10 次，固定抽樣 seed 以可重現
  python experiment/individual_voting.py --repeat 10 --sample_size 48 --sample_seed 42

  # 指定要驗證的 persona ID（一行一個，從現有結果挑選的分層樣本）
  python experiment/individual_voting.py --repeat 10 --persona_ids_file sample_ids.txt

  # 中斷後直接重跑相同指令即可續跑，checkpoint 自動偵測
  # 重設 checkpoint：rm results/.checkpoint_{scenario_id}*.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

# ── 確保 jury 子模組可被匯入（從 jury/ 下的 experiment/ 執行時需要）
# Ensure jury submodules are importable when running from experiment/ inside jury/
_JURY_ROOT = Path(__file__).parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from personas.models import PersonaProfile
from scenarios.loader import ScenarioLoader
from scenarios.models import Scenario

from experiment.baseline import BaselineResultsWriter
from experiment.models import VERDICT_ERROR, VotingRecord, VotingStats
from experiment.parser import ResponseParser
from experiment.reliability import ReliabilityCalculator
from experiment.stats import StatsCalculator
from experiment.voter import OccupationCategoryMapper, PersonaVoter, build_persona_id

# ── 預設路徑
_DEFAULT_PERSONA_POOL = _JURY_ROOT / "personas_output.json"
_DEFAULT_SCENARIO_ID  = "father_theft_medicine"
_DEFAULT_OUTPUT_DIR   = _JURY_ROOT / "results"

# 預設並發執行緒數，對應 config.ini 的 MAX_CONCURRENT_MODEL_CALLS
# Default worker count, aligns with config.ini MAX_CONCURRENT_MODEL_CALLS
_DEFAULT_MAX_WORKERS = 4

# 預設抽樣 random seed（可重現）
# Default RNG seed for stratified/random sub-sampling (reproducible)
_DEFAULT_SAMPLE_SEED = 42

# 預設重複次數：1 = 普通 baseline；>1 = reliability 驗證模式
# Default repeat count: 1 = baseline; >1 = reliability validation mode
_DEFAULT_REPEAT = 1


class CheckpointManager:
    """
    斷點續跑管理器。

    以 JSONL 格式（每行一個 JSON 物件）逐筆追加已完成的 VotingRecord，
    支援 O(1) 追加、O(n) 載入，不需要重寫整個檔案。

    checkpoint key：(persona_id, run_index)，
    讓 reliability 驗證模式（同 persona 多次執行）也能正確續跑。

    檔案命名：
      - repeat=1：.checkpoint_{scenario_id}.jsonl（與舊版相容）
      - repeat>1：.checkpoint_{scenario_id}_reliability_r{repeat}.jsonl

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

    def load_records(self) -> list[VotingRecord]:
        """
        從 checkpoint 載入所有已完成的 VotingRecord。

        Returns:
            VotingRecord 列表；檔案不存在則回傳空 list。
        """
        if not self._path.exists():
            return []
        records: list[VotingRecord] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(VotingRecord(**json.loads(line)))
        return records

    def append(self, record: VotingRecord) -> None:
        """
        追加一筆完成的 VotingRecord 到 checkpoint。

        由主執行緒在 as_completed 迴圈中呼叫，單執行緒寫入，thread-safe。

        Args:
            record: 要追加的 VotingRecord。
        """
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def clear(self) -> None:
        """實驗成功完成後刪除 checkpoint 檔案。"""
        if self._path.exists():
            self._path.unlink()


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
            wanted = self._load_persona_ids(persona_ids_file)
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


class IndividualVotingRunner:
    """
    外觀模式 (Facade Pattern) — 協調個人投票實驗的完整流程。

    支援兩種模式（由 repeat 參數切換）：
      - repeat=1：標準 baseline，每 persona 投一次，更新 baseline_results.json
      - repeat>1：reliability 驗證，每 persona 投 N 次，計算 modal agreement，
                   不更新 baseline（避免污染 Phase 2 結果）

    流程：
      1. 載入 Persona 池（is_valid=True 過濾）
      2. 以 PersonaSampler 選出要參與本次實驗的子集
      3. 載入指定 Scenario
      4. 以 ThreadPoolExecutor 並行對每個 (persona, run_index) 執行投票
      5. 計算統計摘要（與 reliability 摘要，若 repeat>1）
      6. 輸出結果 JSON
      7. 若 repeat=1，更新 baseline_results.json

    Args:
        scenario_id:       要執行的 Scenario ID。
        persona_pool_path: persona pool JSON 的路徑。
        output_dir:        結果 JSON 的輸出目錄。
        max_workers:       並發執行緒數；預設 4，建議不超過 config.ini 的
                           MAX_CONCURRENT_MODEL_CALLS 以避免 API rate limit。
        limit:             只跑前 N 個 persona（煙霧測試用，與抽樣互斥）。
        repeat:            每 persona 的重複測量次數，預設 1；>1 啟用 reliability 驗證。
        sample_size:       隨機抽樣的 persona 數；None = 全部。
        sample_seed:       抽樣 RNG seed，確保可重現。
        persona_ids_file:  指定 persona_id 清單檔；優先於 sample_size。
    """

    def __init__(
        self,
        scenario_id: str = _DEFAULT_SCENARIO_ID,
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
        # None = run all; positive int = run only first N (for smoke testing)
        self._limit             = limit
        self._repeat            = repeat
        self._sample_size       = sample_size
        self._sample_seed       = sample_seed
        self._persona_ids_file  = persona_ids_file

        # 依賴組件（可在測試中替換）
        # Dependency components (replaceable in tests)
        self._persona_loader      = PersonaLoader()
        self._persona_sampler     = PersonaSampler()
        self._category_mapper     = OccupationCategoryMapper()
        self._parser              = ResponseParser()
        self._stats_calculator    = StatsCalculator()
        self._reliability_calc    = ReliabilityCalculator()
        self._baseline_writer     = BaselineResultsWriter()

    @property
    def _is_reliability_mode(self) -> bool:
        """repeat > 1 視為 reliability 驗證模式。"""
        return self._repeat > 1

    def run(self) -> Path:
        """
        執行完整的個人投票實驗。

        Returns:
            輸出 JSON 檔案的路徑。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. 載入 Persona 池
        print(f"Loading persona pool from: {self._persona_pool_path}")
        personas = self._persona_loader.load(self._persona_pool_path)
        print(f"Loaded {len(personas)} valid personas from pool.")

        # 2. 依參數抽樣（隨機 / 指定清單）；--limit 仍保留作為煙霧測試切片
        # Sub-sample (random / id-list); --limit kept for smoke testing
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

        # 4. 建立 PersonaVoter
        voter = PersonaVoter(
            scenario=scenario,
            category_mapper=self._category_mapper,
            parser=self._parser,
        )

        # 5. 初始化 checkpoint（reliability 模式用獨立檔名避免污染 baseline）
        # Init checkpoint (reliability mode uses a separate filename to avoid clobbering baseline)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self._build_checkpoint_path()
        checkpoint      = CheckpointManager(checkpoint_path)
        if checkpoint.exists:
            print(f"Found checkpoint: {checkpoint_path}")
            print(f"  To reset and start over, delete the checkpoint file.")
            # 若要重新開始，請刪除 checkpoint 檔案

        # 6. 並行執行 (persona, run_index) 任務（支援斷點續跑）
        print(f"Starting parallel voting with {self._max_workers} workers...")
        records = self._run_voting_parallel(voter, personas, checkpoint)

        # 7. 計算統計摘要
        stats = self._stats_calculator.calculate(records)

        # 8. 若為 reliability 模式，額外計算 modal agreement 等指標
        reliability_stats = None
        if self._is_reliability_mode:
            reliability_stats = self._reliability_calc.calculate(records, self._repeat)
            self._print_reliability_summary(reliability_stats)

        # 9. 輸出結果 JSON
        output_path = self._write_output(
            records, stats, scenario, timestamp, reliability_stats
        )
        print(f"\nResults written to: {output_path}")

        # 10. 僅在 baseline 模式（repeat=1）更新 baseline_results.json
        # Only update baseline JSON in baseline mode to avoid polluting Phase 2 result
        if not self._is_reliability_mode:
            self._baseline_writer.write(self._scenario_id, stats, timestamp)
            print(f"Baseline dominant verdict ({self._scenario_id}): "
                  f"{stats.dominant_verdict.upper()}")
        else:
            print("Reliability mode: skipping baseline_results.json update.")

        # 11. 成功完成後清除 checkpoint
        checkpoint.clear()

        return output_path

    def _build_checkpoint_path(self) -> Path:
        """
        依模式產生 checkpoint 路徑。

        baseline 模式沿用舊檔名，reliability 模式加上 _reliability_r{N} 後綴，
        避免與 baseline checkpoint 互相覆蓋。
        """
        if self._is_reliability_mode:
            return self._output_dir / (
                f".checkpoint_{self._scenario_id}_reliability_r{self._repeat}.jsonl"
            )
        return self._output_dir / f".checkpoint_{self._scenario_id}.jsonl"

    def _print_reliability_summary(self, rel) -> None:
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

    def _run_voting_parallel(
        self,
        voter: PersonaVoter,
        personas: list[PersonaProfile],
        checkpoint: CheckpointManager,
    ) -> list[VotingRecord]:
        """
        以 ThreadPoolExecutor 並行執行所有 (persona, run_index) 任務，支援斷點續跑。

        reliability 模式下，同一 persona 會被排入 repeat 次任務，每次具有不同
        run_index 與不同 agent_name；不同次之間共用唯讀的 voter / scenario / parser，
        但 TinyPerson Agent 每次都是全新建立，確保 LLM 呼叫間沒有狀態殘留。
        每筆完成後立即寫入 checkpoint；若個別執行緒拋出例外，
        該 (persona, run_index) 的結果被記錄為 parse_error，不影響其他執行緒繼續執行。

        Args:
            voter:      PersonaVoter 實例（唯讀共用，thread-safe）。
            personas:   待投票的 PersonaProfile 列表（每個會被重複 self._repeat 次）。
            checkpoint: CheckpointManager 實例，用於讀取已完成記錄與追加新記錄。

        Returns:
            全部 VotingRecord 列表（已完成 + 本次新完成）。
        """
        # 從 checkpoint 載入已完成 (persona_id, run_index) 集合
        # Load completed (persona_id, run_index) keys from checkpoint
        done_keys         = checkpoint.load_done_keys()
        completed_records = checkpoint.load_records()

        # 展開成全部任務 (persona, run_index)，過濾掉已完成
        # Expand into (persona, run_index) tasks, skip done ones
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

        new_records: list[VotingRecord] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_task = {
                executor.submit(
                    voter.vote,
                    persona,
                    # 加入 run_index 確保同一 persona 多次跑的 agent_name 不衝突
                    # Include run_index so concurrent runs of the same persona get unique names
                    f"Juror_{i:06d}_{persona.occupation.replace(' ', '_')}_r{run_idx:02d}",
                    run_idx,
                ): (persona, run_idx)
                for i, (persona, run_idx) in enumerate(remaining_tasks)
            }
            with tqdm(
                total=len(all_tasks),
                initial=len(done_keys),   # 進度條從已完成任務數開始
                desc="Individual voting",
                unit="run",
            ) as pbar:
                for future in as_completed(future_to_task):
                    persona, run_idx = future_to_task[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        # 單一執行緒失敗不中斷整體實驗，記錄為 parse_error
                        # Single thread failure doesn't abort the experiment; record as parse_error
                        record = self._make_error_record(persona, run_idx, repr(exc))
                    # 主執行緒寫入 checkpoint，single-threaded，thread-safe
                    # Written by main thread in as_completed loop — single-threaded, thread-safe
                    checkpoint.append(record)
                    new_records.append(record)
                    pbar.update(1)

        return completed_records + new_records

    def _make_error_record(
        self,
        persona: PersonaProfile,
        run_index: int,
        error_msg: str,
    ) -> VotingRecord:
        """
        執行緒發生未預期例外時，建立 parse_error 的 VotingRecord。

        Args:
            persona:   發生例外的 PersonaProfile。
            run_index: 該任務的重複測量編號（reliability 模式下 0..repeat-1）。
            error_msg: 例外訊息字串。

        Returns:
            verdict=parse_error 的 VotingRecord。
        """
        return VotingRecord(
            persona_id=build_persona_id(persona),
            ocean_profile=persona.ocean.to_dict(),
            ocean_key=persona.ocean.key(),
            occupation=persona.occupation,
            occupation_category=self._category_mapper.get_category(persona.occupation),
            demographic=persona.demographic.to_dict(),
            verdict=VERDICT_ERROR,
            confidence=-1,
            reason=f"Thread exception: {error_msg}",
            raw_response="",
            run_index=run_index,
        )

    def _write_output(
        self,
        records: list[VotingRecord],
        stats: VotingStats,
        scenario: Scenario,
        timestamp: str,
        reliability_stats=None,
    ) -> Path:
        """
        將投票記錄與統計摘要寫入 JSON 輸出檔案。

        Args:
            records:           所有投票記錄。
            stats:             整體投票統計摘要（reliability 模式下為 N 次彙整）。
            scenario:          執行實驗的 Scenario。
            timestamp:         時間戳記字串（YYYYMMDD_HHMMSS）。
            reliability_stats: ReliabilityStats；reliability 模式才有。

        Returns:
            輸出檔案路徑。
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # reliability 模式用獨立檔名以利區分
        # Reliability mode uses a distinct filename
        if self._is_reliability_mode:
            filename = (
                f"individual_voting_{scenario.scenario_id}"
                f"_reliability_r{self._repeat}_{timestamp}.json"
            )
        else:
            filename = f"individual_voting_{scenario.scenario_id}_{timestamp}.json"
        output_path = self._output_dir / filename

        # 計算 unique persona 數，與 records 總數區分（reliability 下兩者不同）
        # Distinguish unique persona count from total record count (differ in reliability mode)
        unique_personas = len({r.persona_id for r in records})

        output = {
            "metadata": {
                "scenario_id":        scenario.scenario_id,
                "scenario_title":     scenario.title,
                "timestamp":          timestamp,
                "mode":               "reliability" if self._is_reliability_mode else "baseline",
                "repeat":             self._repeat,
                "unique_personas":    unique_personas,
                "total_records":     len(records),
                "sample_size":        self._sample_size,
                "sample_seed":        self._sample_seed,
                "persona_ids_file":   str(self._persona_ids_file) if self._persona_ids_file else None,
                "persona_pool_path":  str(self._persona_pool_path),
            },
            "summary": stats.to_dict(),
            "records": [r.to_dict() for r in records],
        }
        if reliability_stats is not None:
            output["reliability"] = reliability_stats.to_dict()

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return output_path


# ─────────────────────────────────────────────────────────────────────────────
#  CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    """解析命令列引數。"""
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2: Individual voting experiment — "
            # Phase 2：個人投票實驗——
            "each Persona votes on the specified Scenario independently, without group discussion."
            # 每個 Persona 獨立面對指定 Scenario 投票，不進行群體討論。
        )
    )
    parser.add_argument(
        "--scenario_id",
        type=str,
        default=_DEFAULT_SCENARIO_ID,
        help=f"Scenario ID to run (default: {_DEFAULT_SCENARIO_ID})",
        # 要執行的 Scenario ID（預設值如上）
    )
    parser.add_argument(
        "--persona_pool",
        type=Path,
        default=_DEFAULT_PERSONA_POOL,
        help=f"Path to persona pool JSON (default: {_DEFAULT_PERSONA_POOL})",
        # Persona 池 JSON 的路徑（預設值如上）
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Output directory for results JSON (default: {_DEFAULT_OUTPUT_DIR})",
        # 結果 JSON 的輸出目錄（預設值如上）
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=_DEFAULT_MAX_WORKERS,
        help=(
            f"Number of concurrent voting threads (default: {_DEFAULT_MAX_WORKERS}). "
            # 並發投票執行緒數（預設值如上）
            "Align with config.ini MAX_CONCURRENT_MODEL_CALLS to avoid rate limits."
            # 建議與 config.ini 的 MAX_CONCURRENT_MODEL_CALLS 保持一致以避免 API rate limit
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N personas. Omit for full run. Use for smoke testing.",
        # 只跑前 N 個 persona；省略則跑全部。用於煙霧測試。
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=_DEFAULT_REPEAT,
        help=(
            f"Repeat each persona N times for reliability validation "
            f"(default: {_DEFAULT_REPEAT}). N=1 runs the standard baseline; "
            f"N>1 enables reliability mode (modal agreement / confidence SD)."
            # 每個 persona 重複測量 N 次；1 = 普通 baseline，>1 = reliability 驗證模式
        ),
    )
    parser.add_argument(
        "--sample_size",
        type=int,
        default=None,
        help=(
            "Randomly sub-sample N personas before running. "
            "Use with --repeat to test reliability cheaply. "
            "Omit to use the full pool."
            # 隨機抽 N 個 persona；搭配 --repeat 做低成本 reliability 驗證
        ),
    )
    parser.add_argument(
        "--sample_seed",
        type=int,
        default=_DEFAULT_SAMPLE_SEED,
        help=(
            f"RNG seed for --sample_size (default: {_DEFAULT_SAMPLE_SEED}). "
            "Same seed yields the same sample — required for reproducibility."
            # 隨機抽樣 seed，固定值才能可重現
        ),
    )
    parser.add_argument(
        "--persona_ids_file",
        type=Path,
        default=None,
        help=(
            "Path to a text file listing persona_ids (one per line) to test. "
            "Overrides --sample_size. Lines starting with # are treated as comments."
            # 指定要測試的 persona_id 清單檔；優先於 --sample_size
        ),
    )
    return parser.parse_args()


def main() -> None:
    """CLI 入口：解析引數並執行個人投票實驗。"""
    args = _parse_args()
    runner = IndividualVotingRunner(
        scenario_id=args.scenario_id,
        persona_pool_path=args.persona_pool,
        output_dir=args.output_dir,
        max_workers=args.max_workers,
        limit=args.limit,
        repeat=args.repeat,
        sample_size=args.sample_size,
        sample_seed=args.sample_seed,
        persona_ids_file=args.persona_ids_file,
    )
    runner.run()


if __name__ == "__main__":
    main()
