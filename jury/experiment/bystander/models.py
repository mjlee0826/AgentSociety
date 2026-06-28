"""
experiment/bystander/models.py

煙霧實驗個人決策資料結構定義。

設計原則：
  SmokeDecisionRecord  — 單一 Persona 獨自面對煙霧時的決策記錄。
                         平行於 jury/models.py 的 VotingRecord。
  SmokeDecisionStats   — 整體決策統計摘要。
                         平行於 jury/models.py 的 VotingStats。

  決策選項：
    - "report"      — 決定通報煙霧給研究人員
    - "wait"        — 繼續等待觀察，暫不行動
    - "ignore"      — 認為沒有危險，決定忽略
    - "parse_error" — Agent 回應解析失敗

  與 VotingRecord 的對應關係：
    - .decision 欄位（非 .verdict）：煙霧實驗的決策欄位
    - 格式、人口統計欄位完全相同
    - BaseStatsCalculator / BaseReliabilityCalculator 透過 .decision 統一介面處理
"""
from __future__ import annotations

from dataclasses import dataclass

# ── 煙霧決策常數（與 BYSTANDER_SCHEMA.valid_choices 對應）
# Smoke decision constants (matching BYSTANDER_SCHEMA.valid_choices)
SMOKE_DECISION_REPORT = "report"       # 通報煙霧
SMOKE_DECISION_WAIT   = "wait"         # 繼續等待觀察
SMOKE_DECISION_IGNORE = "ignore"       # 決定忽略
SMOKE_DECISION_ERROR  = "parse_error"  # 解析失敗

# ── 浮點數精度
_FLOAT_PRECISION = 4


@dataclass
class SmokeDecisionRecord:
    """
    單一 Persona 獨自面對煙霧時的個人決策記錄。

    平行於 jury/models.py 的 VotingRecord，欄位格式完全對應，
    差異只在 decision（煙霧）vs verdict（陪審團）欄位名稱。

    persona_id 格式：{ocean_key}_{occupation_slug}_{age_group}_{is_parent_int}
    例如：lmhlh_defense_attorney_36-50_1

    run_index：reliability 驗證實驗中同一 persona 重複跑的執行編號（0 起算）。
    """

    persona_id:          str   # 唯一識別碼（與 VotingRecord 格式相同）
    ocean_profile:       dict  # OceanProfile.to_dict()
    ocean_key:           str   # 五字母縮寫，如 'lmhlh'
    occupation:          str   # 職業原始字串
    occupation_category: str   # 職業類別，如 'legal' / 'medical'
    demographic:         dict  # Demographic.to_dict()
    decision:            str   # "report" / "wait" / "ignore" / "parse_error"
    confidence:          int   # 1–10；解析失敗時為 -1
    reason:              str   # 理由段落；解析失敗時為原始回應
    raw_response:        str   # Agent 的原始回應文字
    run_index:           int = 0  # 重複測量中的執行編號（reliability 驗證用）

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "persona_id":          self.persona_id,
            "run_index":           self.run_index,
            "ocean_profile":       self.ocean_profile,
            "ocean_key":           self.ocean_key,
            "occupation":          self.occupation,
            "occupation_category": self.occupation_category,
            "demographic":         self.demographic,
            "decision":            self.decision,
            "confidence":          self.confidence,
            "reason":              self.reason,
            "raw_response":        self.raw_response,
        }


@dataclass
class SmokeDecisionStats:
    """
    煙霧個人決策的整體統計摘要。

    平行於 jury/models.py 的 VotingStats，但適配三選項的決策格式。

    by_occupation_category 結構：
      { category: { report_count, wait_count, ignore_count, total,
                    report_rate, wait_rate, ignore_rate } }

    by_ocean_dimension 結構：
      { dimension: { high: { count, report_count, ... }, low: { ... } } }
    """

    total:                 int
    report_count:          int
    wait_count:            int
    ignore_count:          int
    parse_error_count:     int
    report_rate:           float
    wait_rate:             float
    ignore_rate:           float
    dominant_decision:     str    # "report" / "wait" / "ignore"（三選項多數決）
    by_occupation_category: dict  # 各職業類別決策分佈
    by_ocean_dimension:    dict   # 各 OCEAN 維度高低對決策傾向的影響

    def to_dict(self) -> dict:
        """序列化為字典供 JSON 輸出。"""
        return {
            "total":                 self.total,
            "report_count":          self.report_count,
            "wait_count":            self.wait_count,
            "ignore_count":          self.ignore_count,
            "parse_error_count":     self.parse_error_count,
            "report_rate":           round(self.report_rate, _FLOAT_PRECISION),
            "wait_rate":             round(self.wait_rate, _FLOAT_PRECISION),
            "ignore_rate":           round(self.ignore_rate, _FLOAT_PRECISION),
            "dominant_decision":     self.dominant_decision,
            "by_occupation_category": self.by_occupation_category,
            "by_ocean_dimension":    self.by_ocean_dimension,
        }
