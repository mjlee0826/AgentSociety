"""
tests/test_individual_voting.py

個人投票模組的單元測試。
測試不呼叫 LLM，只驗證解析邏輯、統計計算、ID 生成等純函式。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ── 確保 jury 子模組可被匯入（從 jury/ 下的 tests/ 執行時需要）
# Ensure jury submodules are importable when running from tests/ inside jury/
_JURY_ROOT = Path(__file__).parent.parent
if str(_JURY_ROOT) not in sys.path:
    sys.path.insert(0, str(_JURY_ROOT))

from experiment.baseline import BaselineResultsWriter
from experiment.models import (
    VERDICT_ERROR,
    VERDICT_GUILTY,
    VERDICT_NOT_GUILTY,
    VotingRecord,
    VotingStats,
)
from experiment.parser import ResponseParser
from experiment.stats import StatsCalculator
from experiment.voter import build_persona_id
from personas.models import Demographic, OceanDescription, OceanProfile, PersonaProfile


# ─────────────────────────────────────────────────────────────────────────────
#  測試輔助：建立假 PersonaProfile / VotingRecord
# ─────────────────────────────────────────────────────────────────────────────

def _make_persona(
    openness="low",
    conscientiousness="low",
    extraversion="low",
    agreeableness="low",
    neuroticism="low",
    occupation="defense attorney",
    age_group="36-50",
    is_parent=True,
) -> PersonaProfile:
    """建立用於測試的最小 PersonaProfile。"""
    ocean = OceanProfile(
        openness=openness,
        conscientiousness=conscientiousness,
        extraversion=extraversion,
        agreeableness=agreeableness,
        neuroticism=neuroticism,
    )
    desc = OceanDescription(
        ocean=ocean,
        description_en="Test description.",
        description_zh="測試描述。",
        is_valid=True,
    )
    return PersonaProfile(
        ocean_description=desc,
        occupation=occupation,
        demographic=Demographic(age_group=age_group, is_parent=is_parent),
    )


def _make_record(
    verdict: str,
    occupation_category: str = "legal",
    ocean_profile: dict | None = None,
) -> VotingRecord:
    """建立用於測試的最小 VotingRecord。"""
    default_ocean = {
        "openness": "low", "conscientiousness": "low", "extraversion": "low",
        "agreeableness": "low", "neuroticism": "low",
    }
    return VotingRecord(
        persona_id="test_id",
        ocean_profile=ocean_profile or default_ocean,
        ocean_key="lllll",
        occupation="defense attorney",
        occupation_category=occupation_category,
        demographic={"age_group": "36-50", "is_parent": True},
        verdict=verdict,
        confidence=7,
        reason="Test reason.",
        raw_response="VERDICT: guilty\nCONFIDENCE: 7\nREASON: Test reason.",
    )


def _make_stats(dominant: str, guilty: int, not_guilty: int) -> VotingStats:
    """建立用於測試的最小 VotingStats。"""
    total = guilty + not_guilty
    return VotingStats(
        total=total,
        guilty_count=guilty,
        not_guilty_count=not_guilty,
        parse_error_count=0,
        guilty_rate=guilty / max(total, 1),
        not_guilty_rate=not_guilty / max(total, 1),
        dominant_verdict=dominant,
        by_occupation_category={},
        by_ocean_dimension={},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ResponseParser 測試
# ─────────────────────────────────────────────────────────────────────────────

class TestResponseParser:
    """驗證 ResponseParser 能正確解析各種格式的回應。"""

    def test_parse_guilty(self):
        """標準 guilty 格式可被正確解析。"""
        text = "VERDICT: guilty\nCONFIDENCE: 8\nREASON: The law is clear."
        verdict, confidence, reason = ResponseParser.parse(text)
        assert verdict == VERDICT_GUILTY
        assert confidence == 8
        assert "law" in reason

    def test_parse_not_guilty(self):
        """標準 not_guilty 格式可被正確解析。"""
        text = "VERDICT: not_guilty\nCONFIDENCE: 6\nREASON: Necessity defense applies."
        verdict, confidence, reason = ResponseParser.parse(text)
        assert verdict == VERDICT_NOT_GUILTY
        assert confidence == 6

    def test_parse_case_insensitive(self):
        """VERDICT 解析對大小寫不敏感。"""
        text = "VERDICT: GUILTY\nCONFIDENCE: 5\nREASON: Some reason."
        verdict, _, _ = ResponseParser.parse(text)
        assert verdict == VERDICT_GUILTY

    def test_parse_missing_verdict_returns_error(self):
        """缺少 VERDICT 欄位時應回傳 parse_error。"""
        text = "CONFIDENCE: 5\nREASON: Some reason."
        verdict, confidence, _ = ResponseParser.parse(text)
        assert verdict == VERDICT_ERROR
        assert confidence == -1

    def test_parse_missing_confidence(self):
        """缺少 CONFIDENCE 欄位時 confidence 為 -1，但 verdict 仍有效。"""
        text = "VERDICT: guilty\nREASON: Some reason."
        verdict, confidence, _ = ResponseParser.parse(text)
        assert verdict == VERDICT_GUILTY
        assert confidence == -1

    def test_parse_confidence_clamped_high(self):
        """超出範圍的 CONFIDENCE 應被截斷至 10。"""
        text = "VERDICT: guilty\nCONFIDENCE: 99\nREASON: reason."
        _, confidence, _ = ResponseParser.parse(text)
        assert confidence == 10

    def test_parse_confidence_clamped_low(self):
        """低於 1 的 CONFIDENCE 應被截斷至 1。"""
        text = "VERDICT: guilty\nCONFIDENCE: 0\nREASON: reason."
        _, confidence, _ = ResponseParser.parse(text)
        assert confidence == 1

    def test_parse_reason_multiline(self):
        """多行 REASON 應能完整擷取。"""
        text = (
            "VERDICT: not_guilty\n"
            "CONFIDENCE: 7\n"
            "REASON: The defendant had no choice.\n"
            "All legal options were exhausted before acting."
        )
        _, _, reason = ResponseParser.parse(text)
        assert "no choice" in reason

    def test_parse_extra_text_before(self):
        """VERDICT 前有其他文字時仍能正確解析。"""
        text = (
            "After careful consideration of the case...\n"
            "VERDICT: not_guilty\nCONFIDENCE: 9\nREASON: necessity."
        )
        verdict, confidence, _ = ResponseParser.parse(text)
        assert verdict == VERDICT_NOT_GUILTY
        assert confidence == 9


# ─────────────────────────────────────────────────────────────────────────────
#  build_persona_id 測試
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildPersonaId:
    """驗證 build_persona_id 的格式與唯一性。"""

    def test_format(self):
        """persona_id 格式應為 {ocean_key}_{occ_slug}_{age_group}_{is_parent}。"""
        persona = _make_persona(occupation="defense attorney", age_group="36-50", is_parent=True)
        pid = build_persona_id(persona)
        assert pid == "lllll_defense_attorney_36-50_1"

    def test_occupation_spaces_replaced(self):
        """職業名稱中的空格應被替換為底線。"""
        persona = _make_persona(occupation="elementary school teacher")
        pid = build_persona_id(persona)
        assert " " not in pid
        assert "elementary_school_teacher" in pid

    def test_is_parent_false(self):
        """is_parent=False 時末尾應為 _0。"""
        persona = _make_persona(is_parent=False)
        pid = build_persona_id(persona)
        assert pid.endswith("_0")

    def test_different_personas_produce_different_ids(self):
        """不同的 Persona 應產出不同的 persona_id。"""
        p1 = _make_persona(occupation="prosecutor",  age_group="25-35", is_parent=False)
        p2 = _make_persona(occupation="pharmacist",  age_group="51-65", is_parent=True)
        assert build_persona_id(p1) != build_persona_id(p2)


# ─────────────────────────────────────────────────────────────────────────────
#  StatsCalculator 測試
# ─────────────────────────────────────────────────────────────────────────────

class TestStatsCalculator:
    """驗證 StatsCalculator 的統計計算邏輯。"""

    def _calc(self, records: list[VotingRecord]) -> VotingStats:
        return StatsCalculator().calculate(records)

    def test_basic_counts(self):
        """基礎計數：3 guilty, 2 not_guilty。"""
        records = (
            [_make_record(VERDICT_GUILTY)] * 3
            + [_make_record(VERDICT_NOT_GUILTY)] * 2
        )
        stats = self._calc(records)
        assert stats.total == 5
        assert stats.guilty_count == 3
        assert stats.not_guilty_count == 2
        assert stats.parse_error_count == 0

    def test_dominant_verdict_guilty(self):
        """多數 guilty 時 dominant_verdict 應為 guilty。"""
        records = [_make_record(VERDICT_GUILTY)] * 4 + [_make_record(VERDICT_NOT_GUILTY)] * 2
        assert self._calc(records).dominant_verdict == VERDICT_GUILTY

    def test_dominant_verdict_not_guilty(self):
        """多數 not_guilty 時 dominant_verdict 應為 not_guilty。"""
        records = [_make_record(VERDICT_GUILTY)] + [_make_record(VERDICT_NOT_GUILTY)] * 5
        assert self._calc(records).dominant_verdict == VERDICT_NOT_GUILTY

    def test_dominant_verdict_tie_goes_to_guilty(self):
        """平局時 dominant_verdict 應為 guilty（≥ 時選 guilty）。"""
        records = [_make_record(VERDICT_GUILTY)] * 3 + [_make_record(VERDICT_NOT_GUILTY)] * 3
        assert self._calc(records).dominant_verdict == VERDICT_GUILTY

    def test_parse_errors_excluded_from_rate(self):
        """parse_error 不計入 guilty_rate / not_guilty_rate 的分母。"""
        records = [
            _make_record(VERDICT_GUILTY),
            _make_record(VERDICT_NOT_GUILTY),
            _make_record(VERDICT_ERROR),
        ]
        stats = self._calc(records)
        assert stats.parse_error_count == 1
        assert abs(stats.guilty_rate - 0.5) < 1e-6

    def test_by_occupation_category(self):
        """各職業類別投票分佈計算正確。"""
        records = [
            _make_record(VERDICT_GUILTY,     occupation_category="legal"),
            _make_record(VERDICT_NOT_GUILTY, occupation_category="legal"),
            _make_record(VERDICT_GUILTY,     occupation_category="medical"),
        ]
        stats = self._calc(records)
        assert stats.by_occupation_category["legal"]["total"] == 2
        assert stats.by_occupation_category["legal"]["guilty_count"] == 1
        assert stats.by_occupation_category["medical"]["total"] == 1
        assert stats.by_occupation_category["medical"]["guilty_count"] == 1

    def test_by_ocean_dimension(self):
        """OCEAN 維度分析：high vs low 分組計算。"""
        high_ocean = {
            "openness": "high", "conscientiousness": "low",
            "extraversion": "low", "agreeableness": "low", "neuroticism": "low",
        }
        low_ocean = {
            "openness": "low", "conscientiousness": "low",
            "extraversion": "low", "agreeableness": "low", "neuroticism": "low",
        }
        records = [
            _make_record(VERDICT_GUILTY,     ocean_profile=high_ocean),
            _make_record(VERDICT_GUILTY,     ocean_profile=high_ocean),
            _make_record(VERDICT_NOT_GUILTY, ocean_profile=low_ocean),
        ]
        openness = self._calc(records).by_ocean_dimension["openness"]
        assert openness["high"]["count"] == 2
        assert openness["high"]["guilty_count"] == 2
        assert openness["low"]["count"] == 1
        assert openness["low"]["guilty_count"] == 0

    def test_empty_records(self):
        """空記錄列表不應崩潰。"""
        stats = self._calc([])
        assert stats.total == 0
        assert stats.guilty_count == 0
        assert stats.not_guilty_count == 0


# ─────────────────────────────────────────────────────────────────────────────
#  VotingRecord.to_dict 測試
# ─────────────────────────────────────────────────────────────────────────────

class TestVotingRecordSerialization:
    """驗證 VotingRecord 可正確序列化為 dict / JSON。"""

    def test_to_dict_keys(self):
        """to_dict() 應包含所有必要欄位。"""
        d = _make_record(VERDICT_GUILTY).to_dict()
        expected_keys = {
            "persona_id", "ocean_profile", "ocean_key", "occupation",
            "occupation_category", "demographic", "verdict", "confidence",
            "reason", "raw_response",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_json_serializable(self):
        """to_dict() 的結果必須可被 json.dumps() 序列化。"""
        try:
            json.dumps(_make_record(VERDICT_NOT_GUILTY).to_dict())
        except TypeError as e:
            pytest.fail(f"to_dict() is not JSON-serializable: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  BaselineResultsWriter 測試
# ─────────────────────────────────────────────────────────────────────────────

class TestBaselineResultsWriter:
    """驗證 BaselineResultsWriter 的讀寫邏輯（使用 tmp_path）。"""

    def test_creates_file_if_not_exists(self, tmp_path):
        """baseline_results.json 不存在時應自動建立。"""
        path = tmp_path / "config" / "baseline_results.json"
        writer = BaselineResultsWriter(path=path)
        writer.write("test_scenario", _make_stats(VERDICT_NOT_GUILTY, 30, 70), "2026-05-13T03:00:00")
        assert path.exists()

    def test_write_correct_content(self, tmp_path):
        """寫入的 JSON 內容應包含 dominant_verdict 和計數。"""
        path = tmp_path / "baseline_results.json"
        writer = BaselineResultsWriter(path=path)
        writer.write("father_theft_medicine", _make_stats(VERDICT_NOT_GUILTY, 30, 70), "2026-05-13T03:00:00")
        with path.open() as f:
            entry = json.load(f)["father_theft_medicine"]
        assert entry["dominant_verdict"] == VERDICT_NOT_GUILTY
        assert entry["guilty_count"] == 30
        assert entry["not_guilty_count"] == 70

    def test_preserves_existing_scenarios(self, tmp_path):
        """寫入新 scenario 時不應覆蓋已有的其他 scenario 記錄。"""
        path = tmp_path / "baseline_results.json"
        path.write_text(
            json.dumps({"existing_scenario": {"dominant_verdict": "guilty"}}),
            encoding="utf-8",
        )
        BaselineResultsWriter(path=path).write(
            "new_scenario", _make_stats(VERDICT_NOT_GUILTY, 10, 90), "2026-05-13T03:00:00"
        )
        with path.open() as f:
            content = json.load(f)
        # 舊記錄應保留；新記錄應存在
        # Old entry preserved; new entry present
        assert content["existing_scenario"]["dominant_verdict"] == "guilty"
        assert "new_scenario" in content
