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
"""
from __future__ import annotations

import argparse
import json
import sys
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
from experiment.models import VotingRecord, VotingStats
from experiment.parser import ResponseParser
from experiment.stats import StatsCalculator
from experiment.voter import OccupationCategoryMapper, PersonaVoter

# ── 預設路徑
_DEFAULT_PERSONA_POOL = _JURY_ROOT / "personas_output.json"
_DEFAULT_SCENARIO_ID  = "father_theft_medicine"
_DEFAULT_OUTPUT_DIR   = _JURY_ROOT / "results"


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
      3. 對每個 Persona 執行個人投票（tqdm 進度條）
      4. 計算統計摘要
      5. 輸出結果 JSON
      6. 更新 baseline_results.json

    Args:
        scenario_id:       要執行的 Scenario ID。
        persona_pool_path: persona pool JSON 的路徑。
        output_dir:        結果 JSON 的輸出目錄。
    """

    def __init__(
        self,
        scenario_id: str = _DEFAULT_SCENARIO_ID,
        persona_pool_path: Path = _DEFAULT_PERSONA_POOL,
        output_dir: Path = _DEFAULT_OUTPUT_DIR,
    ) -> None:
        self._scenario_id       = scenario_id
        self._persona_pool_path = persona_pool_path
        self._output_dir        = output_dir

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

        # 4. 對每個 Persona 執行投票（tqdm 進度條）
        records: list[VotingRecord] = []
        for i, persona in enumerate(
            tqdm(personas, desc="Individual voting", unit="persona")
        ):
            # Agent 名稱需唯一，加上序號確保不重複
            # Agent name must be unique; index suffix ensures uniqueness
            agent_name = f"Juror_{i:04d}_{persona.occupation.replace(' ', '_')}"
            record = voter.vote(persona, agent_name)
            records.append(record)

        # 5. 計算統計摘要
        stats = self._stats_calculator.calculate(records)

        # 6. 輸出結果 JSON
        output_path = self._write_output(records, stats, scenario, timestamp)
        print(f"\nResults written to: {output_path}")

        # 7. 更新 baseline_results.json
        self._baseline_writer.write(self._scenario_id, stats, timestamp)
        print(f"Baseline dominant verdict ({self._scenario_id}): {stats.dominant_verdict.upper()}")

        return output_path

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
    return parser.parse_args()


def main() -> None:
    """CLI 入口：解析引數並執行個人投票實驗。"""
    args = _parse_args()
    runner = IndividualVotingRunner(
        scenario_id=args.scenario_id,
        persona_pool_path=args.persona_pool,
        output_dir=args.output_dir,
    )
    runner.run()


if __name__ == "__main__":
    main()
