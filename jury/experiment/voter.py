"""
experiment/voter.py

Agent 建立與個人投票執行。

包含：
  OccupationCategoryMapper — 從 personas.yaml 建立職業 → 類別映射
  build_persona_id          — 為 PersonaProfile 產出唯一識別碼
  PersonaVoter              — 建立 TinyPerson Agent 並執行投票
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from tinytroupe.agent import TinyPerson

# ── 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from personas.models import PersonaProfile
from scenarios.models import Scenario

from experiment.models import VotingRecord
from experiment.parser import ResponseParser

# ── 預設 YAML 路徑
_PERSONAS_YAML = _JURY_ROOT / "config" / "personas.yaml"

# ── TinyPerson 動作類型
_ACTION_TALK = "TALK"

# ── 投票請求 prompt（Agent 可見，英文）
# Voting request prompt (visible to agent, in English)
_VOTING_PROMPT = (
    "You have read the jury brief above. "
    # 你已閱讀上述陪審團簡報。
    "Now you must cast your individual vote as a juror. "
    # 現在你必須作為陪審員投下你的個人票。
    "No deliberation with others is required — this is your personal verdict alone. "
    # 不需要與他人討論——這是你個人的裁決。
    "\n\n"
    "Respond in EXACTLY the following format, with no additional text before or after:\n"
    # 以精確的以下格式回應，前後不得有額外文字：
    "\n"
    "VERDICT: guilty\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one paragraph explaining your reasoning>\n"
    "\n"
    "OR\n"
    "\n"
    "VERDICT: not_guilty\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one paragraph explaining your reasoning>\n"
    "\n"
    "You MUST choose exactly one of: guilty OR not_guilty. "
    # 你必須選擇有罪或無罪其中之一。
    "No abstentions. No conditional verdicts. Your VERDICT line must contain only 'guilty' or 'not_guilty'."
    # 不得棄權，不得附條件裁決。VERDICT 行只能填 'guilty' 或 'not_guilty'。
)


class OccupationCategoryMapper:
    """
    從 personas.yaml 建立職業 → 類別的映射表，避免硬寫職業清單。

    Args:
        yaml_path: personas.yaml 路徑；預設為 config/personas.yaml。
    """

    def __init__(self, yaml_path: Path = _PERSONAS_YAML) -> None:
        self._mapping: dict[str, str] = {}
        self._load(yaml_path)

    def _load(self, yaml_path: Path) -> None:
        """從 YAML 讀取職業類別，建立 occupation → category 映射。"""
        if not yaml_path.exists():
            return
        with yaml_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        for category, occupations in config.get("occupations", {}).items():
            for occ in occupations:
                self._mapping[occ] = category

    def get_category(self, occupation: str) -> str:
        """
        回傳職業所屬類別；若找不到則回傳 'unknown'。

        Args:
            occupation: 職業字串（須與 personas.yaml 完全一致）。
        """
        return self._mapping.get(occupation, "unknown")


def build_persona_id(persona: PersonaProfile) -> str:
    """
    為 PersonaProfile 產出唯一識別碼。

    格式：{ocean_key}_{occupation_slug}_{age_group}_{is_parent_int}
    例如：lmhlh_defense_attorney_36-50_1

    Args:
        persona: 要產出 ID 的 PersonaProfile。

    Returns:
        唯一識別碼字串。
    """
    occ_slug  = persona.occupation.replace(" ", "_")
    is_parent = int(persona.demographic.is_parent)
    age_group = persona.demographic.age_group
    return f"{persona.ocean.key()}_{occ_slug}_{age_group}_{is_parent}"


class PersonaVoter:
    """
    為單一 PersonaProfile 建立 TinyPerson Agent，執行個人投票並回傳 VotingRecord。

    設計原則：
      - 只建立 Agent，不建立 TinyWorld（無群體互動）
      - Agent persona 由 PersonaProfile.to_agent_prompt() 產出
      - 投票請求使用嚴格格式指令確保可解析性

    Args:
        scenario:        要投票的 Scenario。
        category_mapper: 職業 → 類別的映射器。
        parser:          回應解析器。
    """

    def __init__(
        self,
        scenario: Scenario,
        category_mapper: OccupationCategoryMapper,
        parser: ResponseParser,
    ) -> None:
        self._scenario        = scenario
        self._category_mapper = category_mapper
        self._parser          = parser

    def vote(
        self,
        persona: PersonaProfile,
        agent_name: str,
        run_index: int = 0,
    ) -> VotingRecord:
        """
        為指定 Persona 建立 Agent，執行投票，回傳 VotingRecord。

        Args:
            persona:    要投票的 PersonaProfile。
            agent_name: TinyPerson 的唯一識別名稱。
            run_index:  reliability 驗證中的重複執行編號（0 起算）；
                        單次實驗預設 0。

        Returns:
            包含投票結果的 VotingRecord。
        """
        agent = self._build_agent(persona, agent_name)
        raw   = self._get_raw_response(agent)

        verdict, confidence, reason = self._parser.parse(raw)
        persona_id = build_persona_id(persona)
        category   = self._category_mapper.get_category(persona.occupation)

        return VotingRecord(
            persona_id=persona_id,
            ocean_profile=persona.ocean.to_dict(),
            ocean_key=persona.ocean.key(),
            occupation=persona.occupation,
            occupation_category=category,
            demographic=persona.demographic.to_dict(),
            verdict=verdict,
            confidence=confidence,
            reason=reason,
            raw_response=raw,
            run_index=run_index,
        )

    def _build_agent(self, persona: PersonaProfile, agent_name: str) -> TinyPerson:
        """建立具有完整 persona 的 TinyPerson Agent（無 TinyWorld）。"""
        # 從 age_group 字串計算中間值年齡（例如 "36-50" → 43）
        # Compute midpoint age from age_group string (e.g., "36-50" → 43)
        low, high = persona.demographic.age_group.split("-")
        midpoint_age = (int(low) + int(high)) // 2

        agent = TinyPerson(name=agent_name)
        agent.define("age", midpoint_age)
        # 年齡：由 age_group 中間值計算
        agent.define("occupation", persona.occupation)
        # 職業：來自 personas.yaml 職業清單
        agent.define("personality", persona.to_agent_prompt())
        # 人格：OCEAN 描述 + 職業 + 人口統計背景

        return agent

    def _get_raw_response(self, agent: TinyPerson) -> str:
        """
        讓 Agent 閱讀 Scenario 後投票，回傳原始回應文字。

        流程：
          1. listen(scenario_description) — 僅接收情境，不觸發行動
          2. listen_and_act(voting_prompt) — 請求投票，觸發行動
          3. pop_actions_and_get_contents_for("TALK") — 提取 TALK 動作的文字
        """
        # 將情境描述注入 Agent 記憶（不觸發行動）
        # Inject scenario description into agent memory without triggering action
        agent.listen(self._scenario.description_en)

        # 請求投票（觸發行動）
        # Request vote (triggers action generation)
        agent.listen_and_act(_VOTING_PROMPT)

        # 提取最後一個 TALK 動作的文字
        # Extract text from the last TALK action
        raw = agent.pop_actions_and_get_contents_for(_ACTION_TALK, only_last_action=True)
        return raw if isinstance(raw, str) else str(raw)
