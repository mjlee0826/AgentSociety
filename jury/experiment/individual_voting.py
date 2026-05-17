"""
Phase 2 執行入口：個人投票實驗（無群體討論）。

每個 is_valid=True 的 Persona 單獨面對指定 Scenario，
記錄其個人 VERDICT / CONFIDENCE / REASON，
並輸出統計摘要與 baseline_results.json 供後續暗樁實驗使用。

用法：
  cd jury
  python experiment/individual_voting.py
  python experiment/individual_voting.py --scenario_id father_theft_medicine
  python experiment/individual_voting.py --scenario_id father_theft_medicine \\
      --persona_pool personas_output.json --output_dir results
  python experiment/individual_voting.py --max_workers 8
  python experiment/individual_voting.py --limit 5          # 煙霧測試
  # 中斷後直接重跑相同指令即可續跑，checkpoint 自動偵測
  # 重設 checkpoint：rm results/.checkpoint_{scenario_id}.jsonl
"""
from __future__ import annotations

import argparse
import json
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
from experiment.stats import StatsCalculator
from experiment.voter import OccupationCategoryMapper, PersonaVoter, build_persona_id

# ── 預設路徑
_DEFAULT_PERSONA_POOL = _JURY_ROOT / "personas_output.json"
_DEFAULT_SCENARIO_ID  = "father_theft_medicine"
_DEFAULT_OUTPUT_DIR   = _JURY_ROOT / "results"

# 預設並發執行緒數，對應 config.ini 的 MAX_CONCURRENT_MODEL_CALLS
# Default worker count, aligns with config.ini MAX_CONCURRENT_MODEL_CALLS
_DEFAULT_MAX_WORKERS = 4


class CheckpointManager:
    """
    斷點續跑管理器。

    以 JSONL 格式（每行一個 JSON 物件）逐筆追加已完成的 VotingRecord，
    支援 O(1) 追加、O(n) 載入，不需要重寫整個檔案。

    checkpoint 檔案命名規則：results/.checkpoint_{scenario_id}.jsonl
    實驗成功完成後自動刪除；中途中斷則保留供下次繼續。

    Args:
        path: checkpoint 檔案的完整路徑。
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def exists(self) -> bool:
        """checkpoint 檔案是否存在。"""
        return self._path.exists()

    def load_done_ids(self) -> set[str]:
        """
        從 checkpoint 載入已完成的 persona_id 集合。

        Returns:
            已完成的 persona_id set；檔案不存在則回傳空 set。
        """
        if not self._path.exists():
            return set()
        done: set[str] = set()
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(json.loads(line)["persona_id"])
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


class IndividualVotingRunner:
    """
    外觀模式 (Facade Pattern) — 協調個人投票實驗的完整流程。

    流程：
      1. 載入 Persona 池（is_valid=True 過濾）
      2. 載入指定 Scenario
      3. 以 ThreadPoolExecutor 並行對每個 Persona 執行個人投票
      4. 計算統計摘要
      5. 輸出結果 JSON
      6. 更新 baseline_results.json

    Args:
        scenario_id:       要執行的 Scenario ID。
        persona_pool_path: persona pool JSON 的路徑。
        output_dir:        結果 JSON 的輸出目錄。
        max_workers:       並發執行緒數；預設 4，建議不超過 config.ini 的
                           MAX_CONCURRENT_MODEL_CALLS 以避免 API rate limit。
    """

    def __init__(
        self,
        scenario_id: str = _DEFAULT_SCENARIO_ID,
        persona_pool_path: Path = _DEFAULT_PERSONA_POOL,
        output_dir: Path = _DEFAULT_OUTPUT_DIR,
        max_workers: int = _DEFAULT_MAX_WORKERS,
        limit: int | None = None,
    ) -> None:
        self._scenario_id       = scenario_id
        self._persona_pool_path = persona_pool_path
        self._output_dir        = output_dir
        self._max_workers       = max_workers
        # None = 跑全部；正整數 = 只跑前 N 個（煙霧測試用）
        # None = run all; positive int = run only first N (for smoke testing)
        self._limit             = limit

        # 依賴組件（可在測試中替換）
        # Dependency components (replaceable in tests)
        self._persona_loader    = PersonaLoader()
        self._category_mapper   = OccupationCategoryMapper()
        self._parser            = ResponseParser()
        self._stats_calculator  = StatsCalculator()
        self._baseline_writer   = BaselineResultsWriter()

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
        if self._limit is not None:
            personas = personas[: self._limit]
            print(f"Loaded {len(personas)} valid personas (limited to {self._limit}).")
        else:
            print(f"Loaded {len(personas)} valid personas.")

        # 2. 載入 Scenario
        loader   = ScenarioLoader()
        scenario = loader.load_by_id(self._scenario_id)
        print(f"Scenario loaded: [{scenario.scenario_id}] {scenario.title}")

        # 3. 建立 PersonaVoter
        voter = PersonaVoter(
            scenario=scenario,
            category_mapper=self._category_mapper,
            parser=self._parser,
        )

        # 4. 初始化 checkpoint（輸出目錄需先建立）
        self._output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self._output_dir / f".checkpoint_{self._scenario_id}.jsonl"
        checkpoint = CheckpointManager(checkpoint_path)
        if checkpoint.exists:
            print(f"Found checkpoint: {checkpoint_path}")
            print(f"  To reset and start over, delete the checkpoint file.")
            # 若要重新開始，請刪除 checkpoint 檔案

        # 5. 並行對每個 Persona 執行投票（支援斷點續跑）
        print(f"Starting parallel voting with {self._max_workers} workers...")
        records = self._run_voting_parallel(voter, personas, checkpoint)

        # 6. 計算統計摘要
        stats = self._stats_calculator.calculate(records)

        # 7. 輸出結果 JSON
        output_path = self._write_output(records, stats, scenario, timestamp)
        print(f"\nResults written to: {output_path}")

        # 8. 更新 baseline_results.json
        self._baseline_writer.write(self._scenario_id, stats, timestamp)
        print(f"Baseline dominant verdict ({self._scenario_id}): {stats.dominant_verdict.upper()}")

        # 9. 成功完成後清除 checkpoint
        checkpoint.clear()

        return output_path

    def _run_voting_parallel(
        self,
        voter: PersonaVoter,
        personas: list[PersonaProfile],
        checkpoint: CheckpointManager,
    ) -> list[VotingRecord]:
        """
        以 ThreadPoolExecutor 並行執行所有 Persona 的投票，支援斷點續跑。

        每個 Persona 在獨立執行緒中建立自己的 TinyPerson Agent 並呼叫 LLM，
        各執行緒之間不共用 Agent 實例，僅共用唯讀的 voter、scenario、parser。
        每筆完成後立即寫入 checkpoint；若個別執行緒拋出例外，
        該 Persona 的結果被記錄為 parse_error，不影響其他執行緒繼續執行。

        Args:
            voter:      PersonaVoter 實例（唯讀共用，thread-safe）。
            personas:   全部待投票的 PersonaProfile 列表（含已完成的）。
            checkpoint: CheckpointManager 實例，用於讀取已完成記錄與追加新記錄。

        Returns:
            全部 VotingRecord 列表（已完成 + 本次新完成）。
        """
        # 從 checkpoint 載入已完成記錄，過濾出尚未執行的 persona
        # Load completed records from checkpoint, filter out already-done personas
        done_ids = checkpoint.load_done_ids()
        completed_records = checkpoint.load_records()

        if done_ids:
            print(f"Resuming: {len(done_ids)} already done, {len(personas) - len(done_ids)} remaining.")

        remaining = [p for p in personas if build_persona_id(p) not in done_ids]

        new_records: list[VotingRecord] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_persona = {
                executor.submit(
                    voter.vote,
                    persona,
                    f"Juror_{i:04d}_{persona.occupation.replace(' ', '_')}",
                ): (i, persona)
                for i, persona in enumerate(remaining)
            }
            with tqdm(
                total=len(personas),
                initial=len(done_ids),   # 進度條從已完成數量開始
                desc="Individual voting",
                unit="persona",
            ) as pbar:
                for future in as_completed(future_to_persona):
                    i, persona = future_to_persona[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        # 單一執行緒失敗不中斷整體實驗，記錄為 parse_error
                        # Single thread failure doesn't abort the experiment; record as parse_error
                        record = self._make_error_record(persona, repr(exc))
                    # 主執行緒寫入 checkpoint，single-threaded，thread-safe
                    # Written by main thread in as_completed loop — single-threaded, thread-safe
                    checkpoint.append(record)
                    new_records.append(record)
                    pbar.update(1)

        return completed_records + new_records

    def _make_error_record(self, persona: PersonaProfile, error_msg: str) -> VotingRecord:
        """
        執行緒發生未預期例外時，建立 parse_error 的 VotingRecord。

        Args:
            persona:   發生例外的 PersonaProfile。
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
        )

    def _write_output(
        self,
        records: list[VotingRecord],
        stats: VotingStats,
        scenario: Scenario,
        timestamp: str,
    ) -> Path:
        """
        將投票記錄與統計摘要寫入 JSON 輸出檔案。

        Args:
            records:   所有投票記錄。
            stats:     統計摘要。
            scenario:  執行實驗的 Scenario。
            timestamp: 時間戳記字串（YYYYMMDD_HHMMSS）。

        Returns:
            輸出檔案路徑。
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename    = f"individual_voting_{scenario.scenario_id}_{timestamp}.json"
        output_path = self._output_dir / filename

        output = {
            "metadata": {
                "scenario_id": scenario.scenario_id,
                "scenario_title": scenario.title,
                "timestamp": timestamp,
                "total_personas": len(records),
                "persona_pool_path": str(self._persona_pool_path),
            },
            "summary": stats.to_dict(),
            "records": [r.to_dict() for r in records],
        }

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
    )
    runner.run()


if __name__ == "__main__":
    main()
