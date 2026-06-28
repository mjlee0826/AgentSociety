"""
experiment/bystander/voter.py

煙霧實驗個人決策 Agent（SmokePersonaVoter）。

設計原則：
  SmokePersonaVoter 是 GenericDecisionVoter 的 thin wrapper，
  固定使用 BYSTANDER_SCHEMA 與 _SMOKE_VOTING_PROMPT（煙霧決策格式）。
  vote() 回傳 SmokeDecisionRecord 而非 tuple，維持對外清晰介面。

  平行於 jury/voter.py 的 PersonaVoter，差異只在 schema 與 prompt。
"""
from __future__ import annotations

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
from experiment.shared.decision_voter import GenericDecisionVoter
from experiment.shared.parser import ResponseParser
from experiment.shared.mappers import OccupationCategoryMapper
from experiment.shared.utils import build_persona_id
from experiment.bystander.models import SMOKE_DECISION_ERROR, SmokeDecisionRecord

# ── 煙霧決策請求 prompt（Agent 可見，英文）
# Smoke decision request prompt (visible to agent, in English)
_SMOKE_VOTING_PROMPT = (
    "You have read the scenario description above. "
    # 你已閱讀上述情境描述。
    "You are now alone in a waiting room and you notice smoke filling the room. "
    # 你現在獨自在等待室，注意到煙霧正在瀰漫房間。
    "You must decide what to do RIGHT NOW, on your own. "
    # 你必須當下獨自決定要做什麼。
    "This is your personal decision — there are no other people around to consult. "
    # 這是你的個人決策——周圍沒有其他人可以商量。
    "\n\n"
    "Respond in EXACTLY the following format, with no additional text before or after:\n"
    # 以精確的以下格式回應，前後不得有額外文字：
    "\n"
    "ACTION: report\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one paragraph explaining your reasoning>\n"
    "\n"
    "OR\n"
    "\n"
    "ACTION: wait\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one paragraph explaining your reasoning>\n"
    "\n"
    "OR\n"
    "\n"
    "ACTION: ignore\n"
    "CONFIDENCE: <integer 1-10>\n"
    "REASON: <one paragraph explaining your reasoning>\n"
    "\n"
    "You MUST choose exactly one of: report, wait, OR ignore. "
    # 你必須選擇通報、等待、忽略其中之一。
    "- report: You decide to go inform the researcher about the smoke immediately.\n"
    # 通報：你決定立即去通知研究人員煙霧的情況。
    "- wait:   You decide to stay and observe for now, hoping it will clear up.\n"
    # 等待：你決定繼續待著觀察，希望情況會好轉。
    "- ignore: You decide this is nothing to worry about and return to what you were doing.\n"
    # 忽略：你決定這沒什麼好擔心的，繼續做你之前在做的事。
    "Your ACTION line must contain ONLY 'report', 'wait', or 'ignore'."
    # ACTION 行只能填 'report'、'wait' 或 'ignore'。
)


class SmokePersonaVoter:
    """
    為單一 PersonaProfile 建立 TinyPerson Agent，獨自面對煙霧做決策，
    回傳 SmokeDecisionRecord。

    平行於 jury/voter.py 的 PersonaVoter。
    GenericDecisionVoter 的 thin wrapper，固定使用 BYSTANDER_SCHEMA + _SMOKE_VOTING_PROMPT。

    Args:
        scenario:        要面對的煙霧 Scenario。
        category_mapper: 職業 → 類別的映射器。
        parser:          ResponseParser 實例（已用 BYSTANDER_SCHEMA 初始化）。
    """

    def __init__(
        self,
        scenario: Scenario,
        category_mapper: OccupationCategoryMapper,
        parser: ResponseParser,
    ) -> None:
        self._category_mapper = category_mapper
        self._generic_voter   = GenericDecisionVoter(
            scenario=scenario,
            schema=BYSTANDER_SCHEMA,
            decision_prompt=_SMOKE_VOTING_PROMPT,
            parser=parser,
        )

    def vote(
        self,
        persona: PersonaProfile,
        agent_name: str,
        run_index: int = 0,
    ) -> SmokeDecisionRecord:
        """
        為指定 Persona 建立 Agent，獨自面對煙霧決策，回傳 SmokeDecisionRecord。

        Args:
            persona:    要決策的 PersonaProfile。
            agent_name: TinyPerson 的唯一識別名稱。
            run_index:  reliability 驗證中的重複執行編號（0 起算）。

        Returns:
            包含決策結果的 SmokeDecisionRecord。
        """
        decision, confidence, reason, raw = self._generic_voter.vote(persona, agent_name)
        persona_id = build_persona_id(persona)
        category   = self._category_mapper.get_category(persona.occupation)

        return SmokeDecisionRecord(
            persona_id=persona_id,
            ocean_profile=persona.ocean.to_dict(),
            ocean_key=persona.ocean.key(),
            occupation=persona.occupation,
            occupation_category=category,
            demographic=persona.demographic.to_dict(),
            decision=decision,
            confidence=confidence,
            reason=reason,
            raw_response=raw,
            run_index=run_index,
        )
