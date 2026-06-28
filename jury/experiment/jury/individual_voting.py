"""
experiment/jury/individual_voting.py

Phase 2 執行入口：陪審團個人投票實驗（無群體討論）。

每個 is_valid=True 的 Persona 單獨面對指定 Scenario，
記錄其個人 VERDICT / CONFIDENCE / REASON，
並輸出統計摘要與 baseline_results.json 供後續暗樁實驗使用。

支援 reliability 驗證模式：以 --repeat N 讓每個 Persona 重複投票 N 次，
搭配 --sample_size 或 --persona_ids_file 抽樣子集，用於量化 LLM
stochasticity 對個人裁決的污染（modal agreement rate / confidence SD）。

用法（baseline）：
  cd jury
  python experiment/jury/individual_voting.py
  python experiment/jury/individual_voting.py --scenario_id father_theft_medicine
  python experiment/jury/individual_voting.py --max_workers 8
  python experiment/jury/individual_voting.py --limit 5          # 煙霧測試

用法（reliability 驗證）：
  python experiment/jury/individual_voting.py --repeat 10 --sample_size 48 --sample_seed 42
  python experiment/jury/individual_voting.py --repeat 10 --persona_ids_file sample_ids.txt

  # 中斷後直接重跑相同指令即可續跑，checkpoint 自動偵測
  # 重設 checkpoint：rm results/.checkpoint_{scenario_id}*.jsonl
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from personas.models import PersonaProfile
from scenarios.models import Scenario

from experiment.shared.schemas import JURY_SCHEMA
from experiment.shared.individual_voting import BaseIndividualVotingRunner
from experiment.shared.mappers import OccupationCategoryMapper
from experiment.shared.parser import ResponseParser
from experiment.shared.reliability import ReliabilityStatsBase
from experiment.shared.utils import build_persona_id

from experiment.jury.baseline import BaselineResultsWriter
from experiment.jury.models import VERDICT_ERROR, VotingRecord, VotingStats
from experiment.jury.voter import PersonaVoter
from experiment.jury.stats import StatsCalculator
from experiment.jury.reliability import ReliabilityCalculator

# ── 預設值
_DEFAULT_SCENARIO_ID  = "father_theft_medicine"
_DEFAULT_PERSONA_POOL = _JURY_ROOT / "personas_output.json"
_DEFAULT_OUTPUT_DIR   = _JURY_ROOT / "results"
_DEFAULT_MAX_WORKERS  = 4
_DEFAULT_SAMPLE_SEED  = 42
_DEFAULT_REPEAT       = 1


class IndividualVotingRunner(BaseIndividualVotingRunner):
    """
    陪審團個人投票實驗執行器。

    繼承 BaseIndividualVotingRunner（Template Method），
    實作所有陪審團 domain-specific hooks：
      - 使用 PersonaVoter（JURY_SCHEMA + VERDICT prompt）
      - 輸出 VotingRecord / VotingStats
      - baseline 模式（repeat=1）更新 baseline_results.json
      - reliability 模式（repeat>1）不更新 baseline

    Args 同 BaseIndividualVotingRunner。
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
        super().__init__(
            scenario_id=scenario_id,
            persona_pool_path=persona_pool_path,
            output_dir=output_dir,
            max_workers=max_workers,
            limit=limit,
            repeat=repeat,
            sample_size=sample_size,
            sample_seed=sample_seed,
            persona_ids_file=persona_ids_file,
        )
        self._stats_calculator = StatsCalculator()
        self._reliability_calc = ReliabilityCalculator()
        self._baseline_writer  = BaselineResultsWriter()

    # ── Abstract hooks 實作

    @property
    def _schema(self):
        """陪審團使用 JURY_SCHEMA。"""
        return JURY_SCHEMA

    def _create_voter(self, scenario: Scenario, category_mapper: OccupationCategoryMapper,
                      parser: ResponseParser) -> PersonaVoter:
        """建立 PersonaVoter（固定使用 JURY_SCHEMA + VERDICT prompt）。"""
        return PersonaVoter(scenario=scenario, category_mapper=category_mapper, parser=parser)

    def _make_error_record(self, persona: PersonaProfile, run_idx: int,
                            error_msg: str) -> VotingRecord:
        """執行緒例外時建立 parse_error 的 VotingRecord。"""
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
            run_index=run_idx,
        )

    def _record_from_dict(self, d: dict) -> VotingRecord:
        """從 checkpoint raw dict 重建 VotingRecord。"""
        return VotingRecord(**d)

    def _compute_stats(self, records: list[VotingRecord]) -> VotingStats:
        """計算 VotingStats（guilty/not_guilty 分佈）。"""
        return self._stats_calculator.calculate(records)

    def _compute_reliability(self, records: list[VotingRecord],
                              repeat_n: int) -> ReliabilityStatsBase:
        """計算 reliability 統計（modal agreement）。"""
        return self._reliability_calc.calculate(records, repeat_n)

    def _agent_name_for(self, i: int, persona: PersonaProfile, run_idx: int) -> str:
        """產出 Juror Agent 的唯一名稱。"""
        occ = persona.occupation.replace(" ", "_")
        return f"Juror_{i:06d}_{occ}_r{run_idx:02d}"

    def _build_output(self, records: list[VotingRecord], stats: VotingStats,
                      scenario: Scenario, timestamp: str,
                      reliability_stats=None) -> dict:
        """建立 jury individual voting 的 JSON 輸出結構。"""
        output = {
            "metadata": {
                "scenario_id":    scenario.scenario_id,
                "scenario_title": scenario.title,
                "timestamp":      timestamp,
            },
            "summary": stats.to_dict(),
            "records": [r.to_dict() for r in records],
        }
        if reliability_stats is not None:
            output["reliability"] = reliability_stats.to_dict()
        return output

    def _output_filename(self, scenario: Scenario, timestamp: str) -> str:
        """產出輸出檔名。"""
        if self._is_reliability_mode:
            return (
                f"individual_voting_{scenario.scenario_id}"
                f"_reliability_r{self._repeat}_{timestamp}.json"
            )
        return f"individual_voting_{scenario.scenario_id}_{timestamp}.json"

    def _after_run(self, records, stats: VotingStats, scenario_id: str,
                   timestamp: str) -> None:
        """
        baseline 模式下更新 baseline_results.json；reliability 模式跳過。

        覆寫 BaseIndividualVotingRunner 的預設 no-op。
        """
        if not self._is_reliability_mode:
            self._baseline_writer.write(scenario_id, stats, timestamp)
            print(f"Baseline dominant verdict ({scenario_id}): "
                  f"{stats.dominant_verdict.upper()}")
        else:
            print("Reliability mode: skipping baseline_results.json update.")


def _parse_args() -> argparse.Namespace:
    """解析命令列引數。"""
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2: Individual voting experiment — "
            "each Persona votes on the specified Scenario independently."
            # Phase 2：個人投票實驗——每個 Persona 獨立面對指定 Scenario 投票。
        )
    )
    parser.add_argument("--scenario_id", type=str, default=_DEFAULT_SCENARIO_ID,
                        help=f"Scenario ID to run (default: {_DEFAULT_SCENARIO_ID})")
    parser.add_argument("--persona_pool", type=Path, default=_DEFAULT_PERSONA_POOL)
    parser.add_argument("--output_dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max_workers", type=int, default=_DEFAULT_MAX_WORKERS,
                        help="Number of concurrent voting threads.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Run only the first N personas (smoke test).")
    parser.add_argument("--repeat", type=int, default=_DEFAULT_REPEAT,
                        help="Repeat each persona N times for reliability validation.")
    parser.add_argument("--sample_size", type=int, default=None)
    parser.add_argument("--sample_seed", type=int, default=_DEFAULT_SAMPLE_SEED)
    parser.add_argument("--persona_ids_file", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    """CLI 入口。"""
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
