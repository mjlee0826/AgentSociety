"""
experiment/shared/decision_voter.py

泛化個人決策 Agent 執行器。

設計原則：
  GenericDecisionVoter 封裝「建立 TinyPerson → 注入情境 → 請求決策 → 解析回應」
  的共用核心邏輯，使 jury/voter.py（PersonaVoter）與
  bystander/voter.py（SmokePersonaVoter）都能以 thin wrapper 的形式複用。

  與舊版 voter.py 的關鍵差異：
    - 使用 DecisionSchema 參數化決策欄位，不再硬寫 VERDICT/guilty/not_guilty
    - vote() 回傳 (decision, confidence, reason) tuple，
      具體 record 型別由子模組自行包裝
    - decision_prompt 由外部注入，不在此模組定義

  使用範例：
    voter = GenericDecisionVoter(
        scenario=scenario,
        schema=JURY_SCHEMA,
        decision_prompt=_VOTING_PROMPT,
        parser=ResponseParser(JURY_SCHEMA),
    )
    decision, confidence, reason = voter.vote(persona, "Juror_000001_defense_attorney_r00")
"""
from __future__ import annotations

import sys
from pathlib import Path

from tinytroupe.agent import TinyPerson

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from personas.models import PersonaProfile
from scenarios.models import Scenario

from experiment.shared.schemas import DecisionSchema
from experiment.shared.parser import ResponseParser

# ── TinyPerson 動作類型
_ACTION_TALK = "TALK"


class GenericDecisionVoter:
    """
    為單一 PersonaProfile 建立 TinyPerson Agent，注入情境，請求決策，解析回應。

    jury/voter.py（PersonaVoter）與 bystander/voter.py（SmokePersonaVoter）
    都是此 class 的 thin wrapper，各自固定 schema 與 decision_prompt。

    Args:
        scenario:        要面對的 Scenario。
        schema:          決策格式規格（JURY_SCHEMA 或 BYSTANDER_SCHEMA）。
        decision_prompt: 請求決策的 prompt 字串（英文，Agent 可見）。
        parser:          ResponseParser 實例（已用 schema 初始化）。
    """

    def __init__(
        self,
        scenario: Scenario,
        schema: DecisionSchema,
        decision_prompt: str,
        parser: ResponseParser,
    ) -> None:
        self._scenario        = scenario
        self._schema          = schema
        self._decision_prompt = decision_prompt
        self._parser          = parser

    def vote(
        self,
        persona: PersonaProfile,
        agent_name: str,
    ) -> tuple[str, int, str, str]:
        """
        為指定 Persona 建立 Agent，執行決策，回傳解析結果（含原始回應）。

        Args:
            persona:    要決策的 PersonaProfile。
            agent_name: TinyPerson 的唯一識別名稱（呼叫端確保唯一性）。

        Returns:
            (decision, confidence, reason, raw_response) 四元組。
            decision 為 schema.valid_choices 之一，或 schema.error_value。
            raw_response 為 Agent 的原始 LLM 回應文字，供除錯使用。
        """
        agent = self._build_agent(persona, agent_name)
        raw   = self._get_raw_response(agent)
        decision, confidence, reason = self._parser.parse(raw)
        return decision, confidence, reason, raw

    def _build_agent(self, persona: PersonaProfile, agent_name: str) -> TinyPerson:
        """
        建立具有完整 persona 的 TinyPerson Agent（無 TinyWorld）。

        年齡由 age_group 中間值計算（例如 "36-50" → 43）。
        """
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
        讓 Agent 閱讀 Scenario 後做決策，回傳原始回應文字。

        流程：
          1. listen(scenario_description) — 僅接收情境，不觸發行動
          2. listen_and_act(decision_prompt) — 請求決策，觸發行動
          3. pop_actions_and_get_contents_for("TALK") — 提取 TALK 動作的文字
        """
        # 將情境描述注入 Agent 記憶（不觸發行動）
        # Inject scenario description into agent memory without triggering action
        agent.listen(self._scenario.description_en)

        # 請求決策（觸發行動）
        # Request decision (triggers action generation)
        agent.listen_and_act(self._decision_prompt)

        # 提取最後一個 TALK 動作的文字
        # Extract text from the last TALK action
        raw = agent.pop_actions_and_get_contents_for(_ACTION_TALK, only_last_action=True)
        return raw if isinstance(raw, str) else str(raw)
