"""
experiment/bystander/group_models.py

旁觀者效應群體實驗的資料結構定義。

平行於 jury/group_models.py，但適配旁觀者實驗的「逐輪動態記錄」格式。

設計原則：
  BystanderRoundRecord  — 單一 Agent 在某一輪的決策記錄（動態追蹤）。
  BystanderAgentSummary — 單一 Agent 跨全部輪次的決策摘要。
  BystanderGroupStats   — 全體統計摘要，含逐輪通報率。
                          （原名 BystanderStats，更名以區別群體 vs 個人統計）

與陪審團實驗（jury/group_models.py）的關鍵差異：
  - 記錄維度：陪審團為單次最終投票，旁觀者為逐輪動態決策
  - 決策選項：VERDICT(guilty/not_guilty) → ACTION(report/wait/ignore)
  - 分析重點：通報率 × 通報輪次，不是裁決翻轉率

此模組只含資料結構，不含任何業務邏輯。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── 旁觀者決策常數（小寫，對應 BYSTANDER_SCHEMA.valid_choices）
# Bystander decision constants (lowercase, matches BYSTANDER_SCHEMA.valid_choices)
DECISION_REPORT = "report"       # 通報煙霧
DECISION_WAIT   = "wait"         # 繼續等待觀察
DECISION_IGNORE = "ignore"       # 決定忽略（認為沒危險）
DECISION_ERROR  = "parse_error"  # Agent 回應解析失敗

# ── 浮點數精度
_FLOAT_PRECISION = 4


@dataclass
class BystanderRoundRecord:
    """
    單一 Agent 在某一討論輪次的決策記錄。

    每輪每個 Agent 都有一筆 BystanderRoundRecord，
    用於追蹤決策隨討論進行的動態變化。

    Attributes:
        round_num:       第幾輪討論（1-based）。
        agent_index:     Agent 在 shuffle 後的位置索引。
        is_plant:        是否為暗樁 Agent。
        occupation:      正常 Agent 的真實職業 / 暗樁的掩護職業。
        decision:        本輪的決策（"report"/"wait"/"ignore"/"parse_error"）。
        confidence:      決策信心值 1–10；解析失敗為 -1。
        reason:          決策理由（一句話）。
        raw_response:    Agent 的原始 LLM 回應文字。
        is_first_report: 此輪是否是該 Agent 第一次選擇通報（後續輪次標記 False）。
    """

    round_num:       int
    agent_index:     int
    is_plant:        bool
    occupation:      str
    decision:        str
    confidence:      int
    reason:          str
    raw_response:    str
    is_first_report: bool = False

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "round_num":       self.round_num,
            "agent_index":     self.agent_index,
            "is_plant":        self.is_plant,
            "occupation":      self.occupation,
            "decision":        self.decision,
            "confidence":      self.confidence,
            "reason":          self.reason,
            "raw_response":    self.raw_response,
            "is_first_report": self.is_first_report,
        }


@dataclass
class BystanderAgentSummary:
    """
    單一 Agent 跨全部輪次的決策摘要。

    彙整該 Agent 在所有輪次的行為，方便分析個體層級的決策路徑。

    Attributes:
        agent_index:     shuffle 後的位置索引。
        is_plant:        是否為暗樁 Agent。
        occupation:      職業（正常或掩護）。
        reported:        是否在任一輪次選擇通報。
        report_round:    第幾輪第一次通報（None = 從未通報）。
        round_decisions: 各輪決策序列，如 ["wait", "wait", "report"]。
    """

    agent_index:     int
    is_plant:        bool
    occupation:      str
    reported:        bool
    report_round:    int | None
    round_decisions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "agent_index":     self.agent_index,
            "is_plant":        self.is_plant,
            "occupation":      self.occupation,
            "reported":        self.reported,
            "report_round":    self.report_round,
            "round_decisions": self.round_decisions,
        }


@dataclass
class BystanderGroupStats:
    """
    旁觀者效應群體實驗的全體統計摘要。

    平行於 jury/group_models.py 的 GroupDeliberationStats。
    原名 BystanderStats，更名以區別群體與個人統計。

    核心指標：通報率與通報輪次，反映旁觀者效應的強度。
    by_round 記錄逐輪的累積通報率，可觀察效應隨時間的演化。

    Attributes:
        total_agents:       所有 Agent 總數（含暗樁）。
        normal_count:       正常 Agent 數量。
        plant_count:        暗樁 Agent 數量。
        discussion_rounds:  討論輪數。
        reported_count:     有通報的 Agent 數（不計暗樁的通報）。
        report_rate:        正常 Agent 中的通報率。
        mean_report_round:  通報者平均在第幾輪通報（None = 無人通報）。
        by_round:           逐輪統計列表。
        normal_report_rate: 正常 Agent 的通報率（主要研究指標）。
        plant_report_rate:  暗樁 Agent 的通報率（預期接近 0）。
    """

    total_agents:       int
    normal_count:       int
    plant_count:        int
    discussion_rounds:  int
    reported_count:     int
    report_rate:        float
    mean_report_round:  float | None
    by_round:           list[dict]
    normal_report_rate: float
    plant_report_rate:  float

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "total_agents":       self.total_agents,
            "normal_count":       self.normal_count,
            "plant_count":        self.plant_count,
            "discussion_rounds":  self.discussion_rounds,
            "reported_count":     self.reported_count,
            "report_rate":        round(self.report_rate, _FLOAT_PRECISION),
            "mean_report_round":  (
                round(self.mean_report_round, _FLOAT_PRECISION)
                if self.mean_report_round is not None else None
            ),
            "by_round":           self.by_round,
            "normal_report_rate": round(self.normal_report_rate, _FLOAT_PRECISION),
            "plant_report_rate":  round(self.plant_report_rate, _FLOAT_PRECISION),
        }
