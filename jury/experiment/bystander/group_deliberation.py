"""
experiment/bystander/group_deliberation.py

旁觀者效應群體實驗執行入口（SmokeGroupDeliberationRunner）。

複製 Latané & Darley（1968）煙霧瀰漫房間實驗：
  一般 Agent 與被動旁觀暗樁（ConfederateIgnoreStrategy）被放入同一個 TinyWorld，
  面對逐漸飄入的煙霧情境。每輪討論後私下詢問每個 Agent 的當前決策，
  追蹤通報率如何隨輪次、人數與暗樁比例而改變。

與陪審團實驗（jury/group_deliberation.py）的關鍵差異：
  - 決策格式：ACTION: report/wait/ignore（使用 BYSTANDER_SCHEMA）
  - 記錄方式：每輪動態記錄，不是最終一次
  - 暗樁策略：ConfederateIgnoreStrategy（淡化，非說服）
  - 無 baseline_results.json 依賴（無「逆流方向」概念）

平行於 jury/group_deliberation.py 的 GroupDeliberationRunner，
更名自 bystander_experiment.py 的 BystanderExperimentRunner。

用法：
  cd jury
  python experiment/bystander/group_deliberation.py \\
      --scenario_id smoke_filled_room \\
      --normal_count 3 --plant_count 1 --discussion_rounds 5 --seed 42

  # 無暗樁控制組
  python experiment/bystander/group_deliberation.py \\
      --normal_count 1 --plant_count 0 --discussion_rounds 5

輸出檔案：
  results/bystander_{scenario_id}_{normal}n_{plant}p_{rounds}r_{timestamp}.json
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

from agents.confederate_strategy import ConfederateIgnoreStrategy
from agents.factory import AgentFactory
from agents.strategies import PlantStrategy

from experiment.shared.loader import PersonaLoader
from experiment.shared.parser import ResponseParser
from experiment.shared.schemas import BYSTANDER_SCHEMA
from experiment.shared.social_framing import GROUP_SOCIAL_FRAMING_BROADCAST

from experiment.bystander.group_models import (
    DECISION_REPORT,
    DECISION_ERROR,
    BystanderAgentSummary,
    BystanderGroupStats,
    BystanderRoundRecord,
)

from scenarios.loader import ScenarioLoader

# ── 預設路徑
_DEFAULT_PERSONA_POOL = _JURY_ROOT / "personas_output.json"
_DEFAULT_SCENARIO_ID  = "smoke_filled_room"
_DEFAULT_OUTPUT_DIR   = _JURY_ROOT / "results"

# ── 實驗預設參數
_DEFAULT_NORMAL_COUNT  = 3    # 一般受試者預設數量
_DEFAULT_PLANT_COUNT   = 1    # 暗樁預設數量
_DEFAULT_ROUNDS        = 5    # 討論輪數預設值（對應真實實驗約 6 分鐘）
_DEFAULT_SEED          = 42   # 預設 random seed

# ── TinyPerson 動作類型
_ACTION_TALK = "TALK"

# ── 暗樁策略登記表（只含被動旁觀暗樁；新增策略時在此擴充）
# Plant strategy registry (passive confederate only; add more strategies here)
_STRATEGY_REGISTRY: dict[str, type] = {
    "confederate_ignore": ConfederateIgnoreStrategy,
    # 未來可新增其他策略（例如積極推波策略）
    # Future strategies can be added here (e.g. active promotion strategy)
}
_DEFAULT_STRATEGY_NAME = "confederate_ignore"

# ── 煙霧房決策詢問 Prompt（Agent 可見，英文）
# Bystander decision check prompt (visible to agent, in English)
_DECISION_CHECK_PROMPT = (
    "Without announcing anything to the others in the room, "
    # 不要向房間裡的其他人宣布，
    "privately indicate your current decision about the smoke. "
    # 私下表明你目前對於煙霧的決定。
    "This is only for your internal record — others cannot hear this.\n"
    # 這只是你的個人記錄，其他人聽不到。
    "\n"
    "Respond in EXACTLY the following format:\n"
    # 以精確的以下格式回應：
    "\n"
    "ACTION: report\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one sentence explaining why you would leave to report the haze now>\n"
    # ACTION: report — 你打算立即起身離開房間，向走廊研究人員通報煙霧
    "\n"
    "OR\n"
    "\n"
    "ACTION: wait\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one sentence explaining why you are staying and watching for now>\n"
    # ACTION: wait — 你決定暫時留下，繼續觀察其他人的反應後再決定
    "\n"
    "OR\n"
    "\n"
    "ACTION: ignore\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one sentence explaining why you have concluded the haze is not a concern>\n"
    # ACTION: ignore — 你已決定這個霧氣沒有危險，打算繼續等待不做任何動作
    "\n"
    "You MUST choose exactly one of: report, wait, or ignore. "
    # 你必須選擇 report、wait 或 ignore 其中之一。
    "No other responses are accepted. "
    # 不接受其他回應格式。
    "Your ACTION line must contain only 'report', 'wait', or 'ignore'."
    # ACTION 行只能填 'report'、'wait' 或 'ignore'。
)


# ────────────────────────────────────────────────────────────────────────────
#  模組層級輔助函式
# ────────────────────────────────────────────────────────────────────────────

def _resolve_strategy(strategy_name: str) -> PlantStrategy:
    """
    依名稱從策略登記表取得旁觀者實驗用的暗樁策略實例。

    Args:
        strategy_name: 策略名稱字串（如 "confederate_ignore"）。

    Returns:
        PlantStrategy 實例。

    Raises:
        ValueError: 不支援的策略名稱。
    """
    if strategy_name not in _STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy '{strategy_name}'. "
            f"Available: {list(_STRATEGY_REGISTRY.keys())}."
        )
    return _STRATEGY_REGISTRY[strategy_name]()


def _extract_occupation_from_agent_name(agent_name: str) -> str:
    """
    從 AgentFactory 命名格式解析職業字串。

    AgentFactory 命名規則：Juror_{Normal|Plant}_{i}_{occupation_underscored}
    解析方式：以 "_" 分割，跳過前三段，其餘還原為職業。

    Args:
        agent_name: TinyPerson.name。

    Returns:
        職業字串（空格分隔）。
    """
    parts = agent_name.split("_")
    occupation_parts = parts[3:] if len(parts) > 3 else parts
    return " ".join(occupation_parts)


# ────────────────────────────────────────────────────────────────────────────
#  SmokeGroupDeliberationRunner — Facade Pattern
# ────────────────────────────────────────────────────────────────────────────

class SmokeGroupDeliberationRunner:
    """
    外觀模式 (Facade Pattern) — 協調旁觀者效應群體實驗的完整流程。

    平行於 jury/group_deliberation.py 的 GroupDeliberationRunner，
    更名自 bystander_experiment.py 的 BystanderExperimentRunner。

    流程：
      1. 載入 Persona 池（PersonaLoader）與 Scenario（ScenarioLoader）
      2. 建立 AgentFactory（seeded random.Random）
      3. 建立完整受試者群（AgentFactory.create_jury()）
      4. 在 shuffle 前記錄 agent metadata
      5. Shuffle agents 順序（同一 rng）
      6. 建立 TinyWorld，broadcast 情境
      7. 逐輪執行：
           a. world.run(steps=1)              — 一輪群體討論
           b. 逐一私下詢問每個 Agent 的當前決策
           c. 記錄 BystanderRoundRecord
           d. 追蹤首次通報輪次
      8. 計算 BystanderAgentSummary × 每個 Agent
      9. 計算 BystanderGroupStats
      10. 寫入 JSON 輸出

    技術說明：
      私下決策詢問（步驟 7b）使用 agent.listen_and_act()，
      不透過 TinyWorld 廣播，因此其他 Agent 不會知道各人的私下回應。
      這與真實實驗中受試者的「內心決策」類比。

    Args:
        scenario_id:       要執行的 Scenario ID。
        normal_count:      一般受試者數量（>= 1）。
        plant_count:       暗樁受試者數量（>= 0，0 = 純控制組）。
        strategy_name:     暗樁策略名稱（plant_count=0 時不影響結果）。
        discussion_rounds: 討論輪數（>= 1）。
        seed:              random seed（控制取樣與排列順序）。
        output_dir:        結果 JSON 輸出目錄。
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
        # 參數合法性驗證
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

        # 使用 BYSTANDER_SCHEMA 初始化解析器（ACTION: report/wait/ignore）
        # Use BYSTANDER_SCHEMA for parser (ACTION: report/wait/ignore)
        self._persona_loader = PersonaLoader()
        self._parser         = ResponseParser(BYSTANDER_SCHEMA)

    # ------------------------------------------------------------------ #
    #  主執行方法
    # ------------------------------------------------------------------ #

    def run(self) -> Path:
        """
        執行完整的旁觀者效應群體實驗。

        Returns:
            輸出 JSON 檔案的絕對路徑。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. 載入 Persona 池與 Scenario
        # Load persona pool and scenario
        print(f"[1/6] Loading persona pool from: {self._persona_pool_path}")
        personas = self._persona_loader.load(self._persona_pool_path)
        print(f"      Loaded {len(personas)} valid personas.")

        print(f"[2/6] Loading scenario: {self._scenario_id}")
        scenario_loader = ScenarioLoader()
        scenario        = scenario_loader.load_by_id(self._scenario_id)
        print(f"      Scenario: [{scenario.scenario_id}] {scenario.title}")

        # 2. 建立 AgentFactory（seeded RNG）
        # Create AgentFactory with seeded RNG
        rng     = random.Random(self._seed)
        factory = AgentFactory(persona_pool=personas, rng=rng)

        # 3. 建立暗樁設定（ConfederateIgnoreStrategy 忽略 target_verdict）
        # Build plant configs (ConfederateIgnoreStrategy ignores target_verdict)
        plant_configs = []
        if self._plant_count > 0:
            strategy      = _resolve_strategy(self._strategy_name)
            # target_verdict 傳入任意值，ConfederateIgnoreStrategy 不使用此參數
            # Any value works — ConfederateIgnoreStrategy ignores target_verdict
            plant_configs = [(strategy, "IGNORE")] * self._plant_count

        # 4. 建立受試者群（正常在前，暗樁在後）
        # Create participant group (normal first, plants last — will be shuffled)
        print(
            f"[3/6] Creating participants: {self._normal_count} normal + "
            f"{self._plant_count} confederate(s) (strategy={self._strategy_name})"
        )
        agents = factory.create_jury(
            n_normal=self._normal_count,
            plant_configs=plant_configs,
        )

        # 記錄 metadata（在 shuffle 之前）
        # Record metadata before shuffle
        agent_metadata = {
            agent.name: {
                "is_plant":   "_Plant_" in agent.name,
                "occupation": _extract_occupation_from_agent_name(agent.name),
            }
            for agent in agents
        }

        # Shuffle agents 順序（避免位置偏差）
        # Shuffle agent order to eliminate position bias
        rng.shuffle(agents)
        print(f"[4/6] Shuffled {len(agents)} participants.")

        # 5. 建立 TinyWorld 並廣播情境
        # Create TinyWorld and broadcast scenario
        world_name = f"SmokeRoom_{self._scenario_id}_{timestamp}"
        world      = TinyWorld(name=world_name, agents=agents)
        print(f"[5/6] Broadcasting scenario to all participants...")
        world.broadcast(scenario.description_en)
        # 情境廣播注入所有 Agent 記憶，模擬「進入等待室並看到煙霧」
        # Scenario broadcast injects into all agents' memory, simulating "entering the room"
        # 緊接著廣播「公開作答框架」：只讓 Agent 知道發言會被在場他人看見，
        # 不指示其淡化或從眾，讓多元無知（若發生）為內生
        # Then broadcast the public-response framing: it only makes agents aware their
        # statements are seen by others present; it does NOT instruct them to downplay
        # or conform, so pluralistic ignorance (if any) emerges endogenously
        world.broadcast(GROUP_SOCIAL_FRAMING_BROADCAST)

        # 6. 逐輪討論 + 私下決策詢問
        # Per-round discussion + private decision polling
        print(f"[6/6] Running {self._discussion_rounds} discussion round(s)...")

        all_round_records: list[BystanderRoundRecord] = []
        # 追蹤每個 agent 的首次通報輪次（agent.name → round_num 或 None）
        # Track first report round per agent (agent.name → round_num or None)
        first_report_round: dict[str, int | None] = {agent.name: None for agent in agents}

        for round_num in range(1, self._discussion_rounds + 1):
            print(f"      Round {round_num}/{self._discussion_rounds}...")

            # 一輪群體討論（所有 Agent 在 TinyWorld 中互動）
            # One round of group discussion (all agents interact in TinyWorld)
            world.run(steps=1)

            # 逐一私下詢問決策（不廣播，不影響群體討論歷程）
            # Poll each agent privately (not broadcast, does not affect group discussion)
            for idx, agent in enumerate(agents):
                meta       = agent_metadata.get(agent.name, {})
                is_plant   = meta.get("is_plant",   "_Plant_" in agent.name)
                occupation = meta.get("occupation",  _extract_occupation_from_agent_name(agent.name))

                # 私下詢問（只有這個 Agent 收到此 prompt）
                # Private inquiry (only this agent receives this prompt)
                agent.listen_and_act(_DECISION_CHECK_PROMPT)
                raw = agent.pop_actions_and_get_contents_for(_ACTION_TALK, only_last_action=True)
                raw = raw if isinstance(raw, str) else str(raw)

                decision, confidence, reason = self._parser.parse(raw)

                # 判斷是否首次通報
                # Determine if this is the first report for this agent
                is_first_report = False
                if decision == DECISION_REPORT and first_report_round[agent.name] is None:
                    is_first_report                = True
                    first_report_round[agent.name]  = round_num

                record = BystanderRoundRecord(
                    round_num       = round_num,
                    agent_index     = idx,
                    is_plant        = is_plant,
                    occupation      = occupation,
                    decision        = decision,
                    confidence      = confidence,
                    reason          = reason,
                    raw_response    = raw,
                    is_first_report = is_first_report,
                )
                all_round_records.append(record)

        print("      Discussion complete.")

        # 7. 計算每個 Agent 的摘要
        # Compute per-agent summary
        agent_summaries = self._build_agent_summaries(
            agents, agent_metadata, first_report_round, all_round_records
        )

        # 8. 計算全體統計
        # Compute global statistics
        stats = self._compute_stats(agent_summaries)

        # 9. 寫入 JSON 輸出
        # Write JSON output
        output_path = self._write_output(
            round_records   = all_round_records,
            agent_summaries = agent_summaries,
            stats           = stats,
            scenario        = scenario,
            timestamp       = timestamp,
        )
        print(f"\n✓ Results written to: {output_path}")
        return output_path

    # ------------------------------------------------------------------ #
    #  私有方法
    # ------------------------------------------------------------------ #

    def _build_agent_summaries(
        self,
        agents:             list,
        agent_metadata:     dict[str, dict],
        first_report_round: dict[str, int | None],
        all_round_records:  list[BystanderRoundRecord],
    ) -> list[BystanderAgentSummary]:
        """
        從逐輪記錄彙整每個 Agent 的跨輪次決策摘要。

        Args:
            agents:             shuffle 後的 TinyPerson 列表。
            agent_metadata:     agent.name → {is_plant, occupation} 映射。
            first_report_round: agent.name → 首次通報輪次（None = 從未通報）。
            all_round_records:  全部逐輪記錄。

        Returns:
            BystanderAgentSummary 列表，順序與 agents 一致。
        """
        summaries: list[BystanderAgentSummary] = []

        for idx, agent in enumerate(agents):
            meta       = agent_metadata.get(agent.name, {})
            is_plant   = meta.get("is_plant",   "_Plant_" in agent.name)
            occupation = meta.get("occupation",  _extract_occupation_from_agent_name(agent.name))

            # 取出此 Agent 的所有輪次記錄，依輪次排序
            # Extract all round records for this agent, sorted by round
            agent_records = sorted(
                [r for r in all_round_records if r.agent_index == idx],
                key=lambda r: r.round_num,
            )
            round_decisions = [r.decision for r in agent_records]
            report_round    = first_report_round[agent.name]

            summaries.append(BystanderAgentSummary(
                agent_index     = idx,
                is_plant        = is_plant,
                occupation      = occupation,
                reported        = report_round is not None,
                report_round    = report_round,
                round_decisions = round_decisions,
            ))

        return summaries

    def _compute_stats(
        self,
        agent_summaries: list[BystanderAgentSummary],
    ) -> BystanderGroupStats:
        """
        從 BystanderAgentSummary 列表計算全體統計摘要。

        主要研究指標（正常 Agent）：
          - 通報率（normal_report_rate）
          - 平均通報輪次（mean_report_round）
          - 逐輪累積通報率（by_round）

        Args:
            agent_summaries: 所有 Agent 的跨輪次決策摘要。

        Returns:
            BystanderGroupStats 統計摘要。
        """
        normal_summaries = [s for s in agent_summaries if not s.is_plant]
        plant_summaries  = [s for s in agent_summaries if s.is_plant]

        normal_count = len(normal_summaries)
        plant_count  = len(plant_summaries)

        # 正常 Agent 的通報統計（主要研究指標）
        # Normal agent reporting stats (primary research metric)
        normal_reporters      = [s for s in normal_summaries if s.reported]
        normal_reported_count = len(normal_reporters)
        normal_report_rate    = normal_reported_count / max(normal_count, 1)

        # 暗樁通報率（預期接近 0）
        # Plant report rate (expected near 0)
        plant_reporters      = [s for s in plant_summaries if s.reported]
        plant_reported_count = len(plant_reporters)
        plant_report_rate    = plant_reported_count / max(plant_count, 1)

        # 平均通報輪次（只計正常 Agent 中有通報者）
        # Mean report round (only for normal agents who reported)
        report_rounds     = [s.report_round for s in normal_reporters if s.report_round is not None]
        mean_report_round = sum(report_rounds) / len(report_rounds) if report_rounds else None

        # 逐輪累積通報率（基於正常 Agent）
        # Per-round cumulative report rate (based on normal agents)
        by_round: list[dict] = []
        cumulative_reporters = 0
        for round_num in range(1, self._discussion_rounds + 1):
            new_reporters = sum(
                1 for s in normal_summaries if s.report_round == round_num
            )
            cumulative_reporters += new_reporters
            by_round.append({
                "round_num":               round_num,
                "new_reporters":           new_reporters,
                "cumulative_report_count": cumulative_reporters,
                "cumulative_report_rate":  round(
                    cumulative_reporters / max(normal_count, 1), 4
                ),
            })

        return BystanderGroupStats(
            total_agents       = len(agent_summaries),
            normal_count       = normal_count,
            plant_count        = plant_count,
            discussion_rounds  = self._discussion_rounds,
            reported_count     = normal_reported_count,
            report_rate        = normal_report_rate,
            mean_report_round  = mean_report_round,
            by_round           = by_round,
            normal_report_rate = normal_report_rate,
            plant_report_rate  = plant_report_rate,
        )

    def _write_output(
        self,
        round_records:   list[BystanderRoundRecord],
        agent_summaries: list[BystanderAgentSummary],
        stats:           BystanderGroupStats,
        scenario:        object,
        timestamp:       str,
    ) -> Path:
        """
        將逐輪記錄、Agent 摘要與統計摘要寫入 JSON 輸出檔案。

        輸出格式：
          bystander_{scenario_id}_{normal}n_{plant}p_{rounds}r_{timestamp}.json

        Returns:
            輸出檔案的絕對路徑。
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)

        filename = (
            f"bystander_{self._scenario_id}"
            f"_{self._normal_count}n_{self._plant_count}p"
            f"_{self._discussion_rounds}r_{timestamp}.json"
        )
        output_path = self._output_dir / filename

        output = {
            "metadata": {
                "scenario_id":       self._scenario_id,
                "scenario_title":    scenario.title,
                "timestamp":         timestamp,
                "normal_count":      self._normal_count,
                "plant_count":       self._plant_count,
                "strategy_name":     self._strategy_name,
                "discussion_rounds": self._discussion_rounds,
                "seed":              self._seed,
                "persona_pool_path": str(self._persona_pool_path),
            },
            "summary": stats.to_dict(),
            "agents":  [s.to_dict() for s in agent_summaries],
            "rounds":  [r.to_dict() for r in round_records],
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return output_path


# ────────────────────────────────────────────────────────────────────────────
#  CLI 入口
# ────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    """解析命令列引數。"""
    parser = argparse.ArgumentParser(
        description=(
            "Bystander Effect & Pluralistic Ignorance Group Experiment — "
            # 旁觀者效應與多元無知群體實驗——
            "simulates the Latané & Darley (1968) smoke-filled room experiment "
            # 模擬 Latané & Darley（1968）煙霧瀰漫房間實驗，
            "with LLM agents in group discussion."
            # 使用 LLM Agent 進行群體討論。
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--scenario_id",
        type=str,
        default=_DEFAULT_SCENARIO_ID,
        help="Scenario ID (must exist in config/scenarios.yaml).",
        # 要執行的 Scenario ID
    )
    parser.add_argument(
        "--normal_count",
        type=int,
        default=_DEFAULT_NORMAL_COUNT,
        help="Number of normal participants (>= 1).",
        # 一般受試者數量
    )
    parser.add_argument(
        "--plant_count",
        type=int,
        default=_DEFAULT_PLANT_COUNT,
        help="Number of confederate planted agents (>= 0; 0 = control group).",
        # 暗樁數量；0 = 無暗樁控制組
    )
    parser.add_argument(
        "--strategy_name",
        type=str,
        default=_DEFAULT_STRATEGY_NAME,
        choices=list(_STRATEGY_REGISTRY.keys()),
        help="Confederate influence strategy.",
        # 暗樁影響策略
    )
    parser.add_argument(
        "--discussion_rounds",
        type=int,
        default=_DEFAULT_ROUNDS,
        help="Number of discussion rounds.",
        # 討論輪數
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=_DEFAULT_SEED,
        help="Random seed for reproducibility.",
        # 確保可重現的 random seed
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Directory to write result JSON.",
        # 結果 JSON 輸出目錄
    )
    parser.add_argument(
        "--persona_pool",
        type=Path,
        default=_DEFAULT_PERSONA_POOL,
        help="Path to persona pool JSON file.",
        # Persona 池 JSON 路徑
    )
    return parser.parse_args()


def main() -> None:
    """CLI 入口：解析引數並執行旁觀者效應群體實驗。"""
    args = _parse_args()
    runner = SmokeGroupDeliberationRunner(
        scenario_id       = args.scenario_id,
        normal_count      = args.normal_count,
        plant_count       = args.plant_count,
        strategy_name     = args.strategy_name,
        discussion_rounds = args.discussion_rounds,
        seed              = args.seed,
        output_dir        = args.output_dir,
        persona_pool_path = args.persona_pool,
    )
    runner.run()


if __name__ == "__main__":
    main()
