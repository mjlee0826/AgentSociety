"""
experiment/jury/voter.py

陪審團個人投票 Agent（PersonaVoter）。

設計原則：
  PersonaVoter 是 GenericDecisionVoter 的 thin wrapper，
  固定使用 JURY_SCHEMA 與 _VOTING_PROMPT（陪審員投票格式）。
  vote() 回傳 VotingRecord 而非 tuple，維持向後相容介面。

  核心的「建立 TinyPerson → 注入情境 → 取回應」邏輯由 GenericDecisionVoter 提供。
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

from experiment.shared.schemas import JURY_SCHEMA
from experiment.shared.decision_voter import GenericDecisionVoter
from experiment.shared.parser import ResponseParser
from experiment.shared.mappers import OccupationCategoryMapper
from experiment.shared.utils import build_persona_id
from experiment.jury.models import VERDICT_ERROR, VotingRecord

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


class PersonaVoter:
    """
    為單一 PersonaProfile 建立 TinyPerson Agent，執行個人投票並回傳 VotingRecord。

    GenericDecisionVoter 的 thin wrapper，固定使用 JURY_SCHEMA + _VOTING_PROMPT。

    Args:
        scenario:        要投票的 Scenario。
        category_mapper: 職業 → 類別的映射器。
        parser:          ResponseParser 實例（已用 JURY_SCHEMA 初始化）。
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
            schema=JURY_SCHEMA,
            decision_prompt=_VOTING_PROMPT,
            parser=parser,
        )

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
            run_index:  reliability 驗證中的重複執行編號（0 起算）。

        Returns:
            包含投票結果的 VotingRecord。
        """
        decision, confidence, reason, raw = self._generic_voter.vote(persona, agent_name)
        persona_id = build_persona_id(persona)
        category   = self._category_mapper.get_category(persona.occupation)

        return VotingRecord(
            persona_id=persona_id,
            ocean_profile=persona.ocean.to_dict(),
            ocean_key=persona.ocean.key(),
            occupation=persona.occupation,
            occupation_category=category,
            demographic=persona.demographic.to_dict(),
            verdict=decision,
            confidence=confidence,
            reason=reason,
            raw_response=raw,
            run_index=run_index,
        )
