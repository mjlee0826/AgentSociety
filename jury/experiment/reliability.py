"""
experiment/reliability.py

Test-retest reliability 計算器。

從同一批 persona 重複測量 N 次的 VotingRecord 計算：
  - 每個 persona 的 modal verdict / modal agreement rate / confidence SD
  - 整體 reliability 指標（mean modal agreement、fully consistent rate 等）

用途：驗證個人投票（individual voting）在 LLM stochasticity 下
      是否穩定到可作為 baseline。
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from experiment.models import VERDICT_ERROR, VotingRecord

# ── 浮點 round 精度
_FLOAT_PRECISION = 4


@dataclass
class PersonaReliability:
    """
    單一 persona 在 N 次重複測量下的 reliability 指標。
    """

    persona_id: str
    occupation: str
    occupation_category: str
    ocean_key: str
    run_count: int                  # 實際完成的執行次數（可能 < repeat_n）
    verdict_counts: dict            # {'guilty': k, 'not_guilty': m, 'parse_error': p}
    modal_verdict: str              # 出現次數最多的 verdict
    modal_count: int                # modal verdict 的出現次數
    modal_agreement: float          # modal_count / run_count；1.0 = 完全一致
    is_fully_consistent: bool       # modal_agreement == 1.0
    confidence_mean: float          # 該 persona N 次的 confidence 平均（排除 parse_error）
    confidence_sd: float            # 該 persona N 次的 confidence 樣本標準差

    def to_dict(self) -> dict:
        return {
            "persona_id":          self.persona_id,
            "occupation":          self.occupation,
            "occupation_category": self.occupation_category,
            "ocean_key":           self.ocean_key,
            "run_count":           self.run_count,
            "verdict_counts":      self.verdict_counts,
            "modal_verdict":       self.modal_verdict,
            "modal_count":         self.modal_count,
            "modal_agreement":     round(self.modal_agreement, _FLOAT_PRECISION),
            "is_fully_consistent": self.is_fully_consistent,
            "confidence_mean":     round(self.confidence_mean, _FLOAT_PRECISION),
            "confidence_sd":       round(self.confidence_sd, _FLOAT_PRECISION),
        }


@dataclass
class ReliabilityStats:
    """
    重複測量實驗的整體 reliability 摘要。
    """

    repeat_n: int                          # 設計上每 persona 預計重複次數
    total_personas: int                    # 參與重複測量的 persona 數
    fully_consistent_count: int            # modal_agreement == 1.0 的 persona 數
    fully_consistent_rate: float           # fully_consistent_count / total_personas
    mean_modal_agreement: float            # 所有 persona modal_agreement 的平均
    min_modal_agreement: float             # 最不穩定的 persona 的 modal_agreement
    mean_confidence_sd: float              # 所有 persona confidence_sd 的平均
    modal_agreement_buckets: dict          # modal_agreement 分桶計數
    per_persona: list[PersonaReliability]  # 詳細逐人指標
    by_occupation_category: dict = field(default_factory=dict)
    by_ocean_dimension:    dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "repeat_n":                self.repeat_n,
            "total_personas":          self.total_personas,
            "fully_consistent_count":  self.fully_consistent_count,
            "fully_consistent_rate":   round(self.fully_consistent_rate, _FLOAT_PRECISION),
            "mean_modal_agreement":    round(self.mean_modal_agreement, _FLOAT_PRECISION),
            "min_modal_agreement":     round(self.min_modal_agreement, _FLOAT_PRECISION),
            "mean_confidence_sd":      round(self.mean_confidence_sd, _FLOAT_PRECISION),
            "modal_agreement_buckets": self.modal_agreement_buckets,
            "by_occupation_category":  self.by_occupation_category,
            "by_ocean_dimension":      self.by_ocean_dimension,
            "per_persona":             [p.to_dict() for p in self.per_persona],
        }


# OCEAN 五大維度名稱
# Five OCEAN dimension names
_OCEAN_DIMENSIONS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)


class ReliabilityCalculator:
    """
    從 N 次重複測量的 VotingRecord 計算 reliability 統計。

    流程：
      1. 依 persona_id groupby 收集所有重複測量
      2. 對每個 persona 計算 modal verdict / modal agreement / confidence SD
      3. 聚合成整體指標，並按 occupation_category、OCEAN 維度切片
    """

    def calculate(self, records: list[VotingRecord], repeat_n: int) -> ReliabilityStats:
        """
        Args:
            records:  含 run_index 的所有投票記錄；同一 persona_id 應有多筆。
            repeat_n: 實驗設計上每 persona 預計的重複次數。

        Returns:
            ReliabilityStats 摘要。
        """
        # 依 persona_id groupby
        grouped: dict[str, list[VotingRecord]] = defaultdict(list)
        for r in records:
            grouped[r.persona_id].append(r)

        per_persona = [self._calc_persona(rs) for rs in grouped.values()]

        if not per_persona:
            # 空 records 邊界處理；理論上不會發生
            return ReliabilityStats(
                repeat_n=repeat_n,
                total_personas=0,
                fully_consistent_count=0,
                fully_consistent_rate=0.0,
                mean_modal_agreement=0.0,
                min_modal_agreement=0.0,
                mean_confidence_sd=0.0,
                modal_agreement_buckets={},
                per_persona=[],
            )

        fully_consistent = [p for p in per_persona if p.is_fully_consistent]
        n                = len(per_persona)

        return ReliabilityStats(
            repeat_n=repeat_n,
            total_personas=n,
            fully_consistent_count=len(fully_consistent),
            fully_consistent_rate=len(fully_consistent) / n,
            mean_modal_agreement=sum(p.modal_agreement for p in per_persona) / n,
            min_modal_agreement=min(p.modal_agreement for p in per_persona),
            mean_confidence_sd=sum(p.confidence_sd for p in per_persona) / n,
            modal_agreement_buckets=self._bucketize(per_persona),
            by_occupation_category=self._by_occupation(per_persona),
            by_ocean_dimension=self._by_ocean(grouped),
            per_persona=per_persona,
        )

    def _calc_persona(self, runs: list[VotingRecord]) -> PersonaReliability:
        """
        計算單一 persona 的 reliability 指標。

        Args:
            runs: 同一 persona 的所有重複測量記錄。
        """
        # 依 verdict 計數（含 parse_error）
        verdict_counts = dict(Counter(r.verdict for r in runs))

        # 找出 modal verdict：忽略 parse_error，若全部都是 error 則退而求其次
        # Modal verdict: prefer non-error; if all errors, fall back to error
        non_error = {v: c for v, c in verdict_counts.items() if v != VERDICT_ERROR}
        if non_error:
            modal_verdict, modal_count = max(non_error.items(), key=lambda kv: kv[1])
        else:
            modal_verdict, modal_count = max(verdict_counts.items(), key=lambda kv: kv[1])

        run_count       = len(runs)
        modal_agreement = modal_count / run_count if run_count else 0.0

        # confidence 統計：排除 parse_error（confidence = -1）
        # Confidence stats: exclude parse_error records (confidence = -1)
        valid_conf = [r.confidence for r in runs if r.verdict != VERDICT_ERROR]
        if valid_conf:
            mean = sum(valid_conf) / len(valid_conf)
            # 樣本標準差（n-1）；只有 1 筆時 SD = 0
            if len(valid_conf) > 1:
                sd = math.sqrt(
                    sum((c - mean) ** 2 for c in valid_conf) / (len(valid_conf) - 1)
                )
            else:
                sd = 0.0
        else:
            mean, sd = 0.0, 0.0

        # runs 至少有一筆，取第一筆作為 persona 靜態欄位來源
        head = runs[0]

        return PersonaReliability(
            persona_id=head.persona_id,
            occupation=head.occupation,
            occupation_category=head.occupation_category,
            ocean_key=head.ocean_key,
            run_count=run_count,
            verdict_counts=verdict_counts,
            modal_verdict=modal_verdict,
            modal_count=modal_count,
            modal_agreement=modal_agreement,
            is_fully_consistent=(modal_agreement == 1.0),
            confidence_mean=mean,
            confidence_sd=sd,
        )

    def _bucketize(self, per_persona: list[PersonaReliability]) -> dict:
        """
        將 modal_agreement 分桶計數，方便看分佈。

        桶界：[1.0]、[0.9, 1.0)、[0.8, 0.9)、[0.7, 0.8)、[0.5, 0.7)、[0, 0.5)
        """
        buckets = {
            "1.0":          0,  # 完全一致
            "[0.9, 1.0)":   0,
            "[0.8, 0.9)":   0,
            "[0.7, 0.8)":   0,
            "[0.5, 0.7)":   0,
            "[0.0, 0.5)":   0,  # 嚴重不穩
        }
        for p in per_persona:
            a = p.modal_agreement
            if a == 1.0:
                buckets["1.0"] += 1
            elif a >= 0.9:
                buckets["[0.9, 1.0)"] += 1
            elif a >= 0.8:
                buckets["[0.8, 0.9)"] += 1
            elif a >= 0.7:
                buckets["[0.7, 0.8)"] += 1
            elif a >= 0.5:
                buckets["[0.5, 0.7)"] += 1
            else:
                buckets["[0.0, 0.5)"] += 1
        return buckets

    def _by_occupation(self, per_persona: list[PersonaReliability]) -> dict:
        """按職業類別切片，看是否某些職業更不穩定。"""
        buckets: dict[str, list[PersonaReliability]] = defaultdict(list)
        for p in per_persona:
            buckets[p.occupation_category].append(p)

        result = {}
        for cat, ps in sorted(buckets.items()):
            n = len(ps)
            result[cat] = {
                "count":                 n,
                "mean_modal_agreement":  round(sum(x.modal_agreement for x in ps) / n, _FLOAT_PRECISION),
                "fully_consistent_rate": round(sum(1 for x in ps if x.is_fully_consistent) / n, _FLOAT_PRECISION),
                "mean_confidence_sd":    round(sum(x.confidence_sd  for x in ps) / n, _FLOAT_PRECISION),
            }
        return result

    def _by_ocean(self, grouped: dict[str, list[VotingRecord]]) -> dict:
        """
        按 OCEAN 高低切片：看高 N（神經質）等是否更不穩定。

        需要原始 records 來讀 ocean_profile，所以從 grouped 取第一筆。
        """
        # 先彙整 persona_id → (ocean_profile, PersonaReliability 對應 modal_agreement)
        persona_info: dict[str, dict] = {}
        for pid, runs in grouped.items():
            persona_info[pid] = {
                "ocean": runs[0].ocean_profile,
                "runs":  runs,
            }

        result = {}
        for dim in _OCEAN_DIMENSIONS:
            high_runs: list[VotingRecord] = []
            low_runs:  list[VotingRecord] = []
            for pid, info in persona_info.items():
                level = info["ocean"].get(dim)
                if level == "high":
                    high_runs.extend(info["runs"])
                elif level == "low":
                    low_runs.extend(info["runs"])
            result[dim] = {
                "high": self._slice_reliability(high_runs),
                "low":  self._slice_reliability(low_runs),
            }
        return result

    def _slice_reliability(self, runs: list[VotingRecord]) -> dict:
        """為一個切片（高/低 OCEAN）計算彙總 reliability。"""
        if not runs:
            return {"persona_count": 0, "mean_modal_agreement": 0.0, "fully_consistent_rate": 0.0}

        by_pid: dict[str, list[VotingRecord]] = defaultdict(list)
        for r in runs:
            by_pid[r.persona_id].append(r)

        per_persona = [self._calc_persona(rs) for rs in by_pid.values()]
        n           = len(per_persona)
        return {
            "persona_count":         n,
            "mean_modal_agreement":  round(sum(p.modal_agreement for p in per_persona) / n, _FLOAT_PRECISION),
            "fully_consistent_rate": round(sum(1 for p in per_persona if p.is_fully_consistent) / n, _FLOAT_PRECISION),
        }
