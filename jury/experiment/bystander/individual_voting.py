"""
experiment/bystander/individual_voting.py

煙霧個人決策實驗執行入口（SmokeIndividualVotingRunner）。

每個 is_valid=True 的 Persona 單獨面對煙霧情境，
記錄其個人 ACTION（report/wait/ignore）/ CONFIDENCE / REASON，
並輸出統計摘要作為後續群體實驗的 individual baseline。

支援 reliability 驗證模式：以 --repeat N 讓每個 Persona 重複決策 N 次，
搭配 --sample_size 或 --persona_ids_file 抽樣子集，用於量化 LLM
stochasticity 對個人決策的污染（modal agreement rate / confidence SD）。

平行於 jury/individual_voting.py 的 IndividualVotingRunner，
差異只在使用 BYSTANDER_SCHEMA + SmokePersonaVoter。

用法（baseline）：
  cd jury
  python experiment/bystander/individual_voting.py \\
      --scenario_id smoke_filled_room
  python experiment/bystander/individual_voting.py \\
      --scenario_id smoke_filled_room --max_workers 8

用法（reliability 驗證）：
  python experiment/bystander/individual_voting.py \\
      --scenario_id smoke_filled_room \\
      --repeat 10 --sample_size 48 --sample_seed 42 --max_workers 16

  # 中斷後直接重跑相同指令即可續跑，checkpoint 自動偵測
  # 重設 checkpoint：rm results/.checkpoint_smoke_filled_room_smoke*.jsonl
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

from experiment.shared.schemas import BYSTANDER_SCHEMA
from experiment.shared.individual_voting import BaseIndividualVotingRunner
from experiment.shared.mappers import OccupationCategoryMapper
from experiment.shared.parser import ResponseParser
from experiment.shared.reliability import ReliabilityStatsBase
from experiment.shared.utils import build_persona_id

from experiment.bystander.models import SMOKE_DECISION_ERROR, SmokeDecisionRecord, SmokeDecisionStats
from experiment.bystander.voter import SmokePersonaVoter
from experiment.bystander.stats import SmokeStatsCalculator
from experiment.bystander.reliability import SmokeReliabilityCalculator

# ── 預設值
_DEFAULT_SCENARIO_ID  = "smoke_filled_room"
_DEFAULT_PERSONA_POOL = _JURY_ROOT / "personas_output.json"
_DEFAULT_OUTPUT_DIR   = _JURY_ROOT / "results"
_DEFAULT_MAX_WORKERS  = 4
_DEFAULT_SAMPLE_SEED  = 42
_DEFAULT_REPEAT       = 1


class SmokeIndividualVotingRunner(BaseIndividualVotingRunner):
    """
    煙霧個人決策實驗執行器。

    繼承 BaseIndividualVotingRunner（Template Method），
    實作所有煙霧實驗 domain-specific hooks：
      - 使用 SmokePersonaVoter（BYSTANDER_SCHEMA + ACTION prompt）
      - 輸出 SmokeDecisionRecord / SmokeDecisionStats
      - baseline 模式（repeat=1）輸出個人決策分佈
      - reliability 模式（repeat>1）計算 modal agreement

    平行於 jury/individual_voting.py 的 IndividualVotingRunner。
    無 _after_run 覆寫（煙霧實驗無需更新 baseline_results.json）。

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
        self._stats_calculator = SmokeStatsCalculator()
        self._reliability_calc = SmokeReliabilityCalculator()

    # ── Abstract hooks 實作

    @property
    def _schema(self):
        """煙霧實驗使用 BYSTANDER_SCHEMA（report/wait/ignore）。"""
        return BYSTANDER_SCHEMA

    def _checkpoint_suffix(self) -> str:
        """
        checkpoint 後綴加 '_smoke'，避免與 jury checkpoint 命名衝突。

        覆寫 BaseIndividualVotingRunner 的預設 ""。
        """
        return "_smoke"

    def _create_voter(
        self,
        scenario: Scenario,
        category_mapper: OccupationCategoryMapper,
        parser: ResponseParser,
    ) -> SmokePersonaVoter:
        """建立 SmokePersonaVoter（固定使用 BYSTANDER_SCHEMA + ACTION prompt）。"""
        return SmokePersonaVoter(
            scenario=scenario,
            category_mapper=category_mapper,
            parser=parser,
        )

    def _make_error_record(
        self,
        persona: PersonaProfile,
        run_idx: int,
        error_msg: str,
    ) -> SmokeDecisionRecord:
        """執行緒例外時建立 parse_error 的 SmokeDecisionRecord。"""
        return SmokeDecisionRecord(
            persona_id=build_persona_id(persona),
            ocean_profile=persona.ocean.to_dict(),
            ocean_key=persona.ocean.key(),
            occupation=persona.occupation,
            occupation_category=self._category_mapper.get_category(persona.occupation),
            demographic=persona.demographic.to_dict(),
            decision=SMOKE_DECISION_ERROR,
            confidence=-1,
            reason=f"Thread exception: {error_msg}",
            raw_response="",
            run_index=run_idx,
        )

    def _record_from_dict(self, d: dict) -> SmokeDecisionRecord:
        """從 checkpoint raw dict 重建 SmokeDecisionRecord。"""
        return SmokeDecisionRecord(**d)

    def _compute_stats(
        self, records: list[SmokeDecisionRecord]
    ) -> SmokeDecisionStats:
        """計算 SmokeDecisionStats（report/wait/ignore 分佈）。"""
        return self._stats_calculator.calculate(records)

    def _compute_reliability(
        self,
        records: list[SmokeDecisionRecord],
        repeat_n: int,
    ) -> ReliabilityStatsBase:
        """計算 reliability 統計（modal agreement）。"""
        return self._reliability_calc.calculate(records, repeat_n)

    def _agent_name_for(
        self,
        i: int,
        persona: PersonaProfile,
        run_idx: int,
    ) -> str:
        """產出 Bystander Agent 的唯一名稱。"""
        occ = persona.occupation.replace(" ", "_")
        return f"Bystander_{i:06d}_{occ}_r{run_idx:02d}"

    def _build_output(
        self,
        records: list[SmokeDecisionRecord],
        stats: SmokeDecisionStats,
        scenario: Scenario,
        timestamp: str,
        reliability_stats=None,
    ) -> dict:
        """建立煙霧個人決策的 JSON 輸出結構。"""
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

    # _after_run 不覆寫 — 煙霧實驗無 baseline_results.json 需要更新


def _parse_args() -> argparse.Namespace:
    """解析命令列引數。"""
    parser = argparse.ArgumentParser(
        description=(
            "Bystander individual decision experiment — "
            # 旁觀者個人決策實驗——
            "each Persona independently decides what to do upon seeing smoke."
            # 每個 Persona 獨立面對煙霧情境做決策。
        )
    )
    parser.add_argument(
        "--scenario_id",
        type=str,
        default=_DEFAULT_SCENARIO_ID,
        help=f"Scenario ID to run (default: {_DEFAULT_SCENARIO_ID})",
        # 要執行的 Scenario ID
    )
    parser.add_argument(
        "--persona_pool",
        type=Path,
        default=_DEFAULT_PERSONA_POOL,
        help="Path to persona pool JSON file.",
        # Persona 池 JSON 路徑
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Directory to write result JSON.",
        # 結果 JSON 輸出目錄
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=_DEFAULT_MAX_WORKERS,
        help="Number of concurrent voting threads.",
        # 並發執行緒數
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N personas (smoke test).",
        # 只跑前 N 個 persona（快速煙霧測試用）
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=_DEFAULT_REPEAT,
        help="Repeat each persona N times for reliability validation.",
        # 每個 Persona 重複決策 N 次（reliability 驗證用）
    )
    parser.add_argument(
        "--sample_size",
        type=int,
        default=None,
        help="Randomly sample N personas from the pool.",
        # 從 pool 中隨機抽樣 N 個 Persona
    )
    parser.add_argument(
        "--sample_seed",
        type=int,
        default=_DEFAULT_SAMPLE_SEED,
        help="RNG seed for reproducible sampling.",
        # 抽樣用的 RNG seed（確保可重現）
    )
    parser.add_argument(
        "--persona_ids_file",
        type=Path,
        default=None,
        help="Path to a file with one persona_id per line (overrides --sample_size).",
        # 指定 persona_id 清單檔（優先於 --sample_size）
    )
    return parser.parse_args()


def main() -> None:
    """CLI 入口。"""
    args = _parse_args()
    runner = SmokeIndividualVotingRunner(
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
