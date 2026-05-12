"""
AgentFactory — 統一建立 normal agents 和 plant agents 的工廠。

設計原則：
  - Normal agent：從 PersonaPool 隨機取樣一個 PersonaProfile，
    以 OCEAN 描述、職業、人口統計建立公開 persona。
  - Plant agent：接受 PlantStrategy 和 target_verdict，
    以策略指定的掩護職業建立可見 persona，
    隱藏任務指令透過 agent.define("goal", ...) 注入 system prompt，
    其他 Agent 無法直接讀取 system prompt，只能觀察 plant agent 的發言。

隱藏性保證：
  TinyTroupe 中，Agent 間只能透過對話訊息互動，
  無法直接存取彼此的 system prompt / configuration。
  因此，透過 define() 注入的隱藏任務指令只有該 Agent 本身可見。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Optional

from tinytroupe.agent import TinyPerson

# 確保 jury 子模組可被匯入
# Ensure jury submodules are importable
_JURY_ROOT = Path(__file__).parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from agents.strategies import PlantStrategy
from personas.models import PersonaProfile

# Agent 名稱中的職業欄位分隔符
_NAME_SEPARATOR = "_"


class AgentFactory:
    """
    工廠模式 (Factory Pattern)。

    統一建立 normal agents（從 PersonaPool 隨機取樣）
    和 plant agents（接受 strategy 與 target_verdict）。

    Args:
        persona_pool: 已建立的 PersonaProfile 列表，供 normal agent 取樣。
        rng:          已設定 seed 的 random.Random 實例，確保實驗可重現。
    """

    def __init__(
        self,
        persona_pool: list[PersonaProfile],
        rng: random.Random,
    ) -> None:
        self._pool = persona_pool
        self._rng  = rng

    # ------------------------------------------------------------------ #
    #  Normal Agent
    # ------------------------------------------------------------------ #

    def create_normal_agent(self, name: str) -> TinyPerson:
        """
        從 PersonaPool 隨機取樣一個 PersonaProfile，建立正常陪審員 Agent。

        Agent 的 personality 由 PersonaProfile.to_agent_prompt() 產出，
        包含 OCEAN 行為描述、職業與人口統計，完全公開、無隱藏任務。

        Args:
            name: Agent 的識別名稱（不含職業後綴，工廠內部會補上）。

        Returns:
            已設定 persona 的 TinyPerson 實例。
        """
        persona = self._rng.choice(self._pool)

        # Agent 名稱格式：name_occupation，方便識別
        # Agent name format: name_occupation, for easy identification
        full_name = f"{name}{_NAME_SEPARATOR}{persona.occupation.replace(' ', '_')}"
        agent = TinyPerson(name=full_name)

        # 設定公開可見的人物屬性
        # Set publicly visible persona attributes
        agent.define(
            "age",
            # 從 age_group 字串取中間值（例如 "36-50" → 43）
            # Extract midpoint from age_group string (e.g., "36-50" → 43)
            _midpoint_age(persona.demographic.age_group),
        )
        agent.define(
            "occupation",
            persona.occupation,
            # 職業欄位對其他 Agent 可見（透過對話推斷）
            # Occupation field inferable by other agents (via conversation)
        )
        agent.define(
            "personality",
            persona.to_agent_prompt(),
            # 人格描述由 OCEAN 描述 + 職業 + 年齡層 + 是否為家長組成
            # Personality built from OCEAN description + occupation + age group + parenting status
        )

        return agent

    # ------------------------------------------------------------------ #
    #  Plant Agent
    # ------------------------------------------------------------------ #

    def create_plant_agent(
        self,
        name: str,
        strategy: PlantStrategy,
        target_verdict: str,
        ocean_persona: Optional[PersonaProfile] = None,
    ) -> TinyPerson:
        """
        建立暗樁 Agent。

        可見 persona（其他 Agent 可間接推斷）：
          - 職業由 strategy.cover_occupation 決定（例如 "retired judge"）
          - 年齡由 strategy.cover_age 決定
          - OCEAN 性格描述可選擇性地從 PersonaPool 取樣（ocean_persona）

        隱藏任務（只在 system prompt 中，其他 Agent 無法讀取）：
          - 由 strategy.get_system_prompt(target_verdict) 產出
          - 透過 define("goal", ...) 注入，不出現在公開 persona 欄位

        Args:
            name:           Agent 識別名稱。
            strategy:       暗樁策略實例（例如 AuthorityStrategy()）。
            target_verdict: 推動裁決方向，VERDICT_GUILTY 或 VERDICT_NOT_GUILTY。
            ocean_persona:  可選。從 PersonaPool 取樣的 PersonaProfile，
                            僅取其 OCEAN 行為描述（description_en）作為性格底色；
                            職業與年齡由 strategy 覆蓋，不使用 PersonaProfile 的設定。

        Returns:
            已設定 persona 與隱藏任務的 TinyPerson 實例。
        """
        # Agent 名稱格式：name_strategy_occupation
        # Agent name format: name_strategy_occupation
        cover_occ_slug = strategy.cover_occupation.replace(" ", "_")
        full_name = f"{name}{_NAME_SEPARATOR}{cover_occ_slug}"
        agent = TinyPerson(name=full_name)

        # ── 可見 persona（其他 Agent 可間接推斷）──────────────────────────
        # -- Visible persona (inferable by other agents) --

        agent.define(
            "age",
            strategy.cover_age,
            # 掩護年齡（策略指定），符合退休法官等身份設定
            # Cover age (strategy-specified), consistent with retired judge identity
        )
        agent.define(
            "occupation",
            strategy.cover_occupation,
            # 掩護職業（公開，對其他 Agent 可見）
            # Cover occupation (public, visible to other agents)
        )

        # 組合可見的 personality 字串：
        # 若有 ocean_persona，使用其 OCEAN 描述為性格底色（不含職業/年齡層，避免與掩護設定衝突）；
        # 否則使用最小化的空白描述。
        # Assemble visible personality string:
        # If ocean_persona provided, use its OCEAN description as personality base
        # (without occupation/age to avoid conflict with cover identity);
        # otherwise use a minimal neutral description.
        if ocean_persona is not None:
            ocean_description_en = ocean_persona.ocean_description.description_en
            # OCEAN 行為描述（英文），職業與年齡由掩護身份覆蓋
            # OCEAN behavioral description (English), occupation and age overridden by cover identity
            visible_personality = (
                f"{ocean_description_en} "
                # OCEAN 性格底色（描述行為傾向，不涉及職業）
                f"Professionally, you are a {strategy.cover_occupation}. "
                # 職業：由策略指定的掩護職業
                f"You are {strategy.cover_age} years old."
                # 年齡：由策略指定的掩護年齡
            )
        else:
            visible_personality = (
                # 無 OCEAN 底色時，直接以掩護職業與年齡建立最簡性格
                # Without OCEAN base, build minimal personality from cover occupation and age
                f"You are a {strategy.cover_occupation}, {strategy.cover_age} years old. "
                # 你是一位{strategy.cover_occupation}，{strategy.cover_age}歲。
                "You approach situations with the careful, methodical reasoning expected "
                # 你以謹慎、有條理的推理方式應對情況，
                "of someone with your professional background."
                # 這是你的職業背景所期望的。
            )

        agent.define(
            "personality",
            visible_personality,
            # 公開人格描述，其他 Agent 只能從對話中間接推斷此人設
            # Public personality description; other agents can only infer this indirectly via conversation
        )

        # ── 隱藏任務（只存在於 system prompt，其他 Agent 無法直接存取）──────
        # -- Hidden task (only in system prompt, other agents cannot access directly) --

        hidden_instruction = strategy.get_system_prompt(target_verdict)
        # 透過 define("goal", ...) 注入隱藏任務指令
        # 在 TinyTroupe 中，goal 欄位進入 Agent 的 system prompt，
        # 但其他 Agent 無法讀取彼此的 system prompt，
        # 只能從對話訊息中推斷（plant agent 的指令要求其不得洩漏）
        # Inject hidden task via define("goal", ...)
        # In TinyTroupe, the goal field enters the agent's system prompt,
        # but other agents cannot read each other's system prompt —
        # they can only infer from conversation messages
        # (the plant agent's instruction forbids self-disclosure)
        agent.define("goal", hidden_instruction)

        return agent

    # ------------------------------------------------------------------ #
    #  便利方法：批量建立一組陪審員
    # ------------------------------------------------------------------ #

    def create_jury(
        self,
        n_normal: int,
        plant_configs: list[tuple[PlantStrategy, str]],
        name_prefix: str = "Juror",
    ) -> list[TinyPerson]:
        """
        建立由 n_normal 個正常陪審員和若干暗樁陪審員組成的完整陪審團。

        Args:
            n_normal:      正常陪審員數量。
            plant_configs: 暗樁設定列表，每個元素為 (strategy, target_verdict) tuple。
            name_prefix:   Agent 名稱前綴（預設 "Juror"）。

        Returns:
            TinyPerson 列表，正常陪審員在前，暗樁在後。
            （外部程式應在傳入 TinyWorld 前 shuffle，避免位置偏差。）
        """
        agents: list[TinyPerson] = []

        # 建立正常陪審員
        # Create normal jurors
        for i in range(n_normal):
            agent = self.create_normal_agent(name=f"{name_prefix}_Normal_{i + 1}")
            agents.append(agent)

        # 建立暗樁陪審員
        # Create plant jurors
        for i, (strategy, target_verdict) in enumerate(plant_configs):
            agent = self.create_plant_agent(
                name=f"{name_prefix}_Plant_{i + 1}",
                strategy=strategy,
                target_verdict=target_verdict,
                ocean_persona=self._rng.choice(self._pool),
                # 為暗樁也提供 OCEAN 性格底色，使其行為更自然
                # Also provide OCEAN personality base for plant agent for more natural behavior
            )
            agents.append(agent)

        return agents


# ------------------------------------------------------------------ #
#  模組私有輔助函式
# ------------------------------------------------------------------ #

def _midpoint_age(age_group: str) -> int:
    """
    從 "25-35" 格式的年齡層字串計算中間值整數年齡。

    Args:
        age_group: 格式為 "low-high" 的年齡區間字串。

    Returns:
        中間值整數年齡。
    """
    low, high = age_group.split("-")
    return (int(low) + int(high)) // 2
