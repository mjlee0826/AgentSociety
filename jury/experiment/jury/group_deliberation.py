"""
experiment/jury/group_deliberation.py

Phase 3 執行入口：群體討論實驗（Group Deliberation）。

將指定數量的一般 Agent（從 Persona 池取樣）與暗樁 Agent（使用指定策略）
放入同一個 TinyWorld 進行多輪討論，討論結束後以「公開、依序」方式收集每位 Agent
的最終裁決（後投票者會看到前面已公開的票，還原 Asch 公開作答情境），
以量化暗樁對群體決策的影響。

暗樁的推動方向由 baseline_results.json 自動決定（逆流原則）：
  baseline 有罪 → 暗樁推無罪；baseline 無罪 → 暗樁推有罪。

用法（基本）：
  cd jury
  python experiment/jury/group_deliberation.py
  python experiment/jury/group_deliberation.py --scenario_id father_theft_medicine \\
      --normal_count 10 --plant_count 2 --discussion_rounds 3 --seed 42

用法（無暗樁控制組）：
  python experiment/jury/group_deliberation.py --normal_count 6 --plant_count 0 \\
      --discussion_rounds 3

輸出檔案：
  results/group_deliberation_{scenario_id}_{normal}n_{plant}p_{rounds}r_{timestamp}.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from tinytroupe.environment import TinyWorld

from agents.factory import AgentFactory
from agents.authority_strategy import AuthorityStrategy
from agents.strategies import (
    PlantStrategy,
    VERDICT_GUILTY   as AGENT_VERDICT_GUILTY,    # "GUILTY"（大寫，傳給 AgentFactory）
    VERDICT_NOT_GUILTY as AGENT_VERDICT_NOT_GUILTY, # "NOT_GUILTY"（大寫）
)
from experiment.jury.baseline import BaselineResultsReader
from experiment.jury.group_models import (
    AgentDeliberationRecord,
    GroupDeliberationStats,
    GroupSliceStats,
)
from experiment.jury.models import (
    VERDICT_GUILTY     as EXP_VERDICT_GUILTY,    # "guilty"（小寫，來自 baseline JSON）
    VERDICT_NOT_GUILTY as EXP_VERDICT_NOT_GUILTY, # "not_guilty"（小寫）
    VERDICT_ERROR,
)
from experiment.shared.loader import PersonaLoader
from experiment.shared.parser import ResponseParser
from experiment.shared.social_framing import GROUP_SOCIAL_FRAMING_BROADCAST
from scenarios.loader import ScenarioLoader

# ── 預設路徑
_DEFAULT_PERSONA_POOL = _JURY_ROOT / "personas_output.json"
_DEFAULT_SCENARIO_ID  = "father_theft_medicine"
_DEFAULT_OUTPUT_DIR   = _JURY_ROOT / "results"

# ── 實驗預設參數
_DEFAULT_NORMAL_COUNT  = 10   # 一般陪審員預設數量
_DEFAULT_PLANT_COUNT   = 2    # 暗樁預設數量
_DEFAULT_ROUNDS        = 3    # TinyWorld 討論輪數預設值
_DEFAULT_SEED          = 42   # 預設 random seed（確保可重現）
_DEFAULT_STRATEGY_NAME = "authority"  # 預設暗樁策略

# ── TinyPerson 動作類型
_ACTION_TALK = "TALK"

# ── 暗樁策略登記表（新增策略時只需在此新增，不改 Runner）
# Plant strategy registry (add new strategies here only — no changes to Runner needed)
_STRATEGY_REGISTRY: dict[str, type] = {
    "authority": AuthorityStrategy,
    # 未來可新增其他策略
    # Future strategies can be added here
}

# ── 討論結束後的最終投票請求 prompt（Agent 可見，英文）
# Post-discussion final voting prompt (visible to agent, in English)
_POST_DISCUSSION_VOTING_PROMPT = (
    "The jury deliberation has now concluded. "
    # 陪審團討論現已結束。
    "You have heard all arguments presented by your fellow jurors. "
    # 你已聽取了所有陪審員提出的論點。
    "Now you must cast your individual, final, and binding verdict. "
    # 現在你必須投下你個人的、最終的、有約束力的裁決。
    "Cast the verdict you genuinely arrive at after that deliberation. "
    # 投下你在該討論後真正得出的裁決。
    "\n\n"
    "Respond in EXACTLY the following format, with no additional text before or after:\n"
    # 以精確的以下格式回應，前後不得有額外文字：
    "\n"
    "VERDICT: guilty\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one paragraph explaining your final reasoning after deliberation>\n"
    "\n"
    "OR\n"
    "\n"
    "VERDICT: not_guilty\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one paragraph explaining your final reasoning after deliberation>\n"
    "\n"
    "You MUST choose exactly one of: guilty OR not_guilty. "
    # 你必須選擇有罪或無罪其中之一。
    "No abstentions. No conditional verdicts. "
    # 不得棄權，不得附條件裁決。
    "Your VERDICT line must contain only 'guilty' or 'not_guilty'."
    # VERDICT 行只能填 'guilty' 或 'not_guilty'。
)


def _resolve_strategy(strategy_name: str) -> PlantStrategy:
    """依名稱從策略登記表取得暗樁策略實例。"""
    if strategy_name not in _STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. "
            f"Available strategies: {list(_STRATEGY_REGISTRY.keys())}."
        )
    return _STRATEGY_REGISTRY[strategy_name]()


def _opposite_verdict(baseline_verdict: str) -> str:
    """依 baseline dominant_verdict 計算暗樁的逆流目標裁決。"""
    if baseline_verdict == EXP_VERDICT_GUILTY:
        return AGENT_VERDICT_NOT_GUILTY
    if baseline_verdict == EXP_VERDICT_NOT_GUILTY:
        return AGENT_VERDICT_GUILTY
    raise ValueError(f"Invalid baseline_verdict: '{baseline_verdict}'.")


def _extract_occupation_from_agent_name(agent_name: str) -> str:
    """從 AgentFactory 命名格式中解析職業字串。"""
    parts = agent_name.split("_")
    occupation_parts = parts[3:] if len(parts) > 3 else parts
    return " ".join(occupation_parts)


class GroupDeliberationRunner:
    """
    外觀模式 (Facade Pattern) — 協調群體討論實驗的完整流程。

    Args:
        scenario_id:       要執行的 Scenario ID。
        normal_count:      一般陪審員數量（>= 1）。
        plant_count:       暗樁陪審員數量（>= 0，0 = 純控制組）。
        strategy_name:     暗樁策略名稱。
        discussion_rounds: TinyWorld.run() 的步驟數。
        seed:              控制取樣與排列順序的 random seed。
        output_dir:        結果 JSON 的輸出目錄。
        persona_pool_path: Persona 池 JSON 路徑。
    """

    def __init__(
        self,
        scenario_id:       str  = _DEFAULT_SCENARIO_ID,
        normal_count:      int  = _DEFAULT_NORMAL_COUNT,
        plant_count:       int  = _DEFAULT_PLANT_COUNT,
        strategy_name:     str  = _DEFAULT_STRATEGY_NAME,
        discussion_rounds: int  = _DEFAULT_ROUNDS,
        seed:              int  = _DEFAULT_SEED,
        output_dir:        Path = _DEFAULT_OUTPUT_DIR,
        persona_pool_path: Path = _DEFAULT_PERSONA_POOL,
    ) -> None:
        if normal_count < 1:
            raise ValueError(f"normal_count must be >= 1, got {normal_count}")
        if plant_count < 0:
            raise ValueError(f"plant_count must be >= 0, got {plant_count}")
        if discussion_rounds < 1:
            raise ValueError(f"discussion_rounds must be >= 1, got {discussion_rounds}")

        self._scenario_id       = scenario_id
        self._normal_count      = normal_count
        self._plant_count       = plant_count
        self._strategy_name     = strategy_name
        self._discussion_rounds = discussion_rounds
        self._seed              = seed
        self._output_dir        = Path(output_dir)
        self._persona_pool_path = Path(persona_pool_path)

        self._persona_loader  = PersonaLoader()
        self._parser          = ResponseParser()
        self._baseline_reader = BaselineResultsReader()

    def run(self) -> Path:
        """執行完整的群體討論實驗，回傳輸出 JSON 路徑。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        print(f"[1/8] Reading baseline for scenario: {self._scenario_id}")
        baseline_verdict = self._baseline_reader.read_dominant_verdict(self._scenario_id)
        print(f"      Baseline dominant verdict: {baseline_verdict.upper()}")
        target_verdict = _opposite_verdict(baseline_verdict)
        print(f"      Plant target verdict: {target_verdict}")

        print(f"[2/8] Loading persona pool from: {self._persona_pool_path}")
        personas = self._persona_loader.load(self._persona_pool_path)
        print(f"      Loaded {len(personas)} valid personas.")

        print(f"[3/8] Loading scenario: {self._scenario_id}")
        scenario = ScenarioLoader().load_by_id(self._scenario_id)
        print(f"      Scenario: [{scenario.scenario_id}] {scenario.title}")

        rng     = random.Random(self._seed)
        factory = AgentFactory(persona_pool=personas, rng=rng)

        if self._plant_count > 0:
            strategy      = _resolve_strategy(self._strategy_name)
            plant_configs = [(strategy, target_verdict)] * self._plant_count
        else:
            plant_configs = []

        print(
            f"[4/8] Creating jury: {self._normal_count} normal + "
            f"{self._plant_count} plant(s) (strategy={self._strategy_name})"
        )
        agents = factory.create_jury(
            n_normal=self._normal_count,
            plant_configs=plant_configs,
        )

        agent_metadata = self._build_agent_metadata(agents)
        rng.shuffle(agents)
        print(f"[5/8] Shuffled {len(agents)} agents.")

        world_name = f"JuryRoom_{self._scenario_id}_{timestamp}"
        world      = TinyWorld(name=world_name, agents=agents)

        print(f"[6/8] Broadcasting scenario to {len(agents)} agents...")
        world.broadcast(scenario.description_en)
        # 在討論開始前廣播「公開作答框架」：只讓 Agent 知道發言會被他人看見，
        # 不指示其從眾（避免 demand effect），讓從眾與否為內生
        # Broadcast the public-response framing before deliberation begins: it only
        # makes agents aware their statements are seen by others; it does NOT instruct
        # them to conform (avoiding a demand effect)
        world.broadcast(GROUP_SOCIAL_FRAMING_BROADCAST)

        print(f"[7/8] Running {self._discussion_rounds} discussion round(s)...")
        world.run(steps=self._discussion_rounds)
        print("      Deliberation complete.")

        print(f"[8/8] Polling final verdicts (public, sequential)...")
        records = self._poll_final_verdicts(agents, agent_metadata)
        stats   = self._compute_stats(records)

        output_path = self._write_output(records, stats, scenario, timestamp,
                                          baseline_verdict, target_verdict)
        print(f"\n✓ Results written to: {output_path}")
        return output_path

    def _build_agent_metadata(self, agents: list) -> dict[str, dict]:
        """在 shuffle 前，從 agent.name 建立 metadata 映射表。"""
        metadata: dict[str, dict] = {}
        for agent in agents:
            is_plant   = "_Plant_" in agent.name
            occupation = _extract_occupation_from_agent_name(agent.name)
            metadata[agent.name] = {"is_plant": is_plant, "occupation": occupation}
        return metadata

    def _build_sequential_voting_prompt(self, prior_votes: list[str]) -> str:
        """
        依「目前已公開唱出的裁決」組出本位 Agent 的投票 prompt（公開依序投票）。

        每位 Agent 都會被告知：現在是當眾、輪流唱票，且它的裁決會被其他人聽到。
        若在它之前已有人投票，則再附上「匿名逐票清單」與「目前票數小計」，
        藉此還原 Asch 的公開作答情境——後投票者承受前面多數的壓力。

        重要：此 prompt 只「陳述事實」（誰投了什麼、你的票會被聽到），
              絕不指示 Agent 從眾或向多數靠攏（避免 demand effect）。

        匿名性：以投票順位 Juror #N 呈現，絕不顯示 agent 內部名稱或暗樁身份，
                確保暗樁的隱藏身份不外洩。

        Args:
            prior_votes: 依投票順序累積、已成功解析的裁決字串清單。

        Returns:
            本位 Agent 可見的完整投票 prompt 字串（英文）。
        """
        # 每位投票者共通的「當眾輪流唱票」聲明（Agent 可見，英文）
        # Shared "public, out-loud, in turn" notice for every voter (visible, English)
        turn_notice = (
            "The jurors are now casting their final verdicts out loud, one at a time, "
            # 陪審員現在正一個接一個地當眾唱出最終裁決，
            "for the whole room to hear, and it is now your turn. "
            # 讓整個房間都聽得到，現在輪到你了。
            "Every other juror and everyone else in the room will hear the verdict "
            # 其他每一位陪審員、以及房間裡的所有人，
            "you are about to announce.\n"
            # 都會聽到你接下來宣告的裁決。
        )

        # 若已有人投票，附上匿名逐票清單與票數小計（讓前面多數對後投票者顯著化）
        # If others have voted, append an anonymous per-vote list + running tally
        if prior_votes:
            tally_lines = "\n".join(
                f"  - Juror #{position}: {verdict.upper()}"
                for position, verdict in enumerate(prior_votes, start=1)
            )
            guilty_n     = prior_votes.count(EXP_VERDICT_GUILTY)
            not_guilty_n = prior_votes.count(EXP_VERDICT_NOT_GUILTY)
            turn_notice += (
                "The jurors who have already voted stated the following, in order, "
                # 在你之前已投票的陪審員，依序、
                "for everyone to hear:\n"
                # 當眾表態如下：
                f"{tally_lines}\n"
                f"(So far: {not_guilty_n} for NOT_GUILTY, {guilty_n} for GUILTY.)\n"
                # （目前票數小計：not_guilty {not_guilty_n} 票，guilty {guilty_n} 票。）
            )

        return f"{turn_notice}\n{_POST_DISCUSSION_VOTING_PROMPT}"

    def _poll_final_verdicts(self, agents, agent_metadata) -> list[AgentDeliberationRecord]:
        """
        討論後「公開、依序」收集最終裁決。

        每位 Agent 投票前，會先看到「在它之前已公開投票者」的裁決（匿名 Juror #N，
        不洩漏暗樁身份），且被告知它的裁決會被其他人聽到——以還原 Asch 公開作答情境，
        使後投票者承受前面多數的壓力。投票順序沿用先前 shuffle 後的 agents 順序。

        同時記錄每位 Agent 投票「前」看到的公開票數（prior_*_seen）與順位（vote_position），
        供後續分析「正常 Agent 是在多大的多數壓力下表態」。
        """
        records = []
        prior_votes: list[str] = []   # 依投票順序累積、已成功解析的公開裁決
        for idx, agent in enumerate(agents):
            meta       = agent_metadata.get(agent.name, {})
            is_plant   = meta.get("is_plant", "_Plant_" in agent.name)
            occupation = meta.get("occupation", _extract_occupation_from_agent_name(agent.name))

            # 記錄本位 Agent 投票「前」看到的公開票數（量化它承受的多數壓力）
            prior_guilty     = prior_votes.count(EXP_VERDICT_GUILTY)
            prior_not_guilty = prior_votes.count(EXP_VERDICT_NOT_GUILTY)

            # 組出含「目前公開票數」的投票 prompt，並請求當眾裁決
            voting_prompt = self._build_sequential_voting_prompt(prior_votes)
            agent.listen_and_act(voting_prompt)
            raw = agent.pop_actions_and_get_contents_for(_ACTION_TALK, only_last_action=True)
            raw = raw if isinstance(raw, str) else str(raw)

            verdict, confidence, reason = self._parser.parse(raw)

            # 將本票（若有效）公開加入票數，供後續 Agent 看見
            if verdict in (EXP_VERDICT_GUILTY, EXP_VERDICT_NOT_GUILTY):
                prior_votes.append(verdict)

            records.append(AgentDeliberationRecord(
                agent_index   = idx,
                is_plant      = is_plant,
                persona_id    = None,
                occupation    = occupation,
                ocean_key     = None,
                strategy_name = self._strategy_name if is_plant else None,
                verdict       = verdict,
                confidence    = confidence,
                reason        = reason,
                raw_response  = raw,
                vote_position         = idx + 1,
                prior_guilty_seen     = prior_guilty,
                prior_not_guilty_seen = prior_not_guilty,
            ))
        return records

    def _compute_stats(self, records) -> GroupDeliberationStats:
        """計算三層統計（全體 / 正常 / 暗樁）。"""
        def _slice(subset):
            total        = len(subset)
            guilty_n     = sum(1 for r in subset if r.verdict == EXP_VERDICT_GUILTY)
            not_guilty_n = sum(1 for r in subset if r.verdict == EXP_VERDICT_NOT_GUILTY)
            error_n      = sum(1 for r in subset if r.verdict == VERDICT_ERROR)
            dominant     = EXP_VERDICT_GUILTY if guilty_n >= not_guilty_n else EXP_VERDICT_NOT_GUILTY
            return GroupSliceStats(total=total, guilty_count=guilty_n,
                                   not_guilty_count=not_guilty_n,
                                   parse_error_count=error_n, dominant_verdict=dominant)

        total        = len(records)
        guilty_n     = sum(1 for r in records if r.verdict == EXP_VERDICT_GUILTY)
        not_guilty_n = sum(1 for r in records if r.verdict == EXP_VERDICT_NOT_GUILTY)
        error_n      = sum(1 for r in records if r.verdict == VERDICT_ERROR)
        valid_n      = max(guilty_n + not_guilty_n, 1)
        dominant     = EXP_VERDICT_GUILTY if guilty_n >= not_guilty_n else EXP_VERDICT_NOT_GUILTY

        return GroupDeliberationStats(
            total=total, guilty_count=guilty_n, not_guilty_count=not_guilty_n,
            parse_error_count=error_n, guilty_rate=guilty_n / valid_n,
            not_guilty_rate=not_guilty_n / valid_n, dominant_verdict=dominant,
            normal_stats=_slice([r for r in records if not r.is_plant]),
            plant_stats=_slice([r for r in records if r.is_plant]),
        )

    def _write_output(self, records, stats, scenario, timestamp,
                      baseline_verdict, target_verdict) -> Path:
        """將討論記錄與統計寫入 JSON。"""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"group_deliberation_{self._scenario_id}"
            f"_{self._normal_count}n_{self._plant_count}p"
            f"_{self._discussion_rounds}r_{timestamp}.json"
        )
        output_path = self._output_dir / filename
        output = {
            "metadata": {
                "scenario_id":               self._scenario_id,
                "scenario_title":            scenario.title,
                "timestamp":                 timestamp,
                "normal_count":              self._normal_count,
                "plant_count":               self._plant_count,
                "discussion_rounds":         self._discussion_rounds,
                "strategy_name":             self._strategy_name,
                "seed":                      self._seed,
                "baseline_dominant_verdict": baseline_verdict,
                "target_verdict_for_plants": target_verdict.lower(),
                "persona_pool_path":         str(self._persona_pool_path),
            },
            "summary": stats.to_dict(),
            "agents":  [r.to_dict() for r in records],
        }
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        return output_path


def _parse_args() -> argparse.Namespace:
    """解析命令列引數。"""
    parser = argparse.ArgumentParser(
        description="Phase 3: Group deliberation experiment.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--scenario_id", type=str, default=_DEFAULT_SCENARIO_ID)
    parser.add_argument("--normal_count", type=int, default=_DEFAULT_NORMAL_COUNT)
    parser.add_argument("--plant_count", type=int, default=_DEFAULT_PLANT_COUNT)
    parser.add_argument("--strategy_name", type=str, default=_DEFAULT_STRATEGY_NAME,
                        choices=list(_STRATEGY_REGISTRY.keys()))
    parser.add_argument("--discussion_rounds", type=int, default=_DEFAULT_ROUNDS)
    parser.add_argument("--seed", type=int, default=_DEFAULT_SEED)
    parser.add_argument("--output_dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    parser.add_argument("--persona_pool", type=Path, default=_DEFAULT_PERSONA_POOL)
    return parser.parse_args()


def main() -> None:
    """CLI 入口。"""
    args = _parse_args()
    runner = GroupDeliberationRunner(
        scenario_id=args.scenario_id, normal_count=args.normal_count,
        plant_count=args.plant_count, strategy_name=args.strategy_name,
        discussion_rounds=args.discussion_rounds, seed=args.seed,
        output_dir=args.output_dir, persona_pool_path=args.persona_pool,
    )
    runner.run()


if __name__ == "__main__":
    main()
