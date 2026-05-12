"""
personas 模組的單元測試。
所有 LLM 呼叫均以 unittest.mock.patch 模擬，不需要真實 API key。
"""
from __future__ import annotations

import itertools
import json
import random
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from personas.factory import PersonaGeneratorFactory
from personas.generator import PersonaGenerator
from personas.models import Demographic, OceanProfile, PersonaProfile, ValidationResult
from personas.pool import PersonaPool

# ------------------------------------------------------------------ #
#  測試資料工廠
# ------------------------------------------------------------------ #

def _make_ocean(
    o="medium", c="medium", e="medium", a="medium", n="medium"
) -> OceanProfile:
    return OceanProfile(
        openness=o, conscientiousness=c, extraversion=e,
        agreeableness=a, neuroticism=n,
    )


def _make_demographic(age_group="36-50", is_parent=True) -> Demographic:
    return Demographic(age_group=age_group, is_parent=is_parent)


def _make_persona(is_valid=True) -> PersonaProfile:
    return PersonaProfile(
        ocean=_make_ocean(),
        occupation="police officer",
        demographic=_make_demographic(),
        description_en="A dedicated officer who values order.",
        description_zh="一位重視秩序的盡責警察。",
        is_valid=is_valid,
    )


def _minimal_config() -> dict:
    """最小化設定 dict（2 levels × 5 dims = 32 combos，2 occupations = 64 total）。"""
    return {
        "ocean": {"levels": ["low", "high"]},
        "occupations": {"general": ["truck driver", "retail store clerk"]},
        "demographic": {
            "age_groups": ["25-35", "36-50"],
            "is_parent": [True, False],
        },
        "generation": {
            "model": "gpt-4o-mini",
            "n_occupations": None,
            "random_seed": 0,
            "max_retries": 0,  # 測試中預設不重試，有需要的測試自行覆蓋
        },
    }


def _mock_openai_response(content: str) -> MagicMock:
    """建立模擬 openai ChatCompletion 回應。"""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ------------------------------------------------------------------ #
#  OceanProfile 測試
# ------------------------------------------------------------------ #

class TestOceanProfile:
    def test_key_format(self):
        """key() 回傳各維度首字母串接的 5 字元字串。"""
        ocean = OceanProfile("low", "medium", "high", "low", "medium")
        assert ocean.key() == "lmhlm"

    def test_all_243_combos_unique_keys(self):
        """243 個 OCEAN 組合應產生 243 個不重複的 key。"""
        levels = ["low", "medium", "high"]
        keys = {
            OceanProfile(*combo).key()
            for combo in itertools.product(levels, repeat=5)
        }
        assert len(keys) == 243

    def test_roundtrip(self):
        """to_dict → from_dict 應完整還原所有欄位。"""
        ocean = OceanProfile("low", "high", "medium", "low", "high")
        assert OceanProfile.from_dict(ocean.to_dict()) == ocean


# ------------------------------------------------------------------ #
#  Demographic 測試
# ------------------------------------------------------------------ #

class TestDemographic:
    def test_roundtrip(self):
        demo = Demographic(age_group="51-65", is_parent=False)
        assert Demographic.from_dict(demo.to_dict()) == demo


# ------------------------------------------------------------------ #
#  PersonaProfile 測試
# ------------------------------------------------------------------ #

class TestPersonaProfile:
    def test_roundtrip(self):
        """to_dict → from_dict 應完整還原所有欄位，包含巢狀結構。"""
        persona = _make_persona()
        assert PersonaProfile.from_dict(persona.to_dict()) == persona

    def test_invalid_persona_roundtrip(self):
        persona = _make_persona(is_valid=False)
        assert PersonaProfile.from_dict(persona.to_dict()).is_valid is False


# ------------------------------------------------------------------ #
#  ValidationResult 測試
# ------------------------------------------------------------------ #

class TestValidationResult:
    def test_default_reason_empty(self):
        """通過時 reason 預設為空字串。"""
        r = ValidationResult(is_valid=True)
        assert r.reason == ""

    def test_invalid_has_reason(self):
        r = ValidationResult(is_valid=False, reason="Description contradicts low agreeableness.")
        assert r.is_valid is False
        assert "agreeableness" in r.reason


# ------------------------------------------------------------------ #
#  PersonaPool 儲存 / 載入測試
# ------------------------------------------------------------------ #

class TestPersonaPool:
    def test_save_and_load_valid_only(self):
        """save 後 load 應回傳相同的 PersonaProfile 列表（只含 valid）。"""
        personas = [_make_persona()]
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PersonaPool(
                pool_path=Path(tmpdir) / "pool.json",
                done_keys_path=Path(tmpdir) / "done.json",
            )
            pool.save(personas)
            loaded = pool.load()
        assert loaded == personas

    def test_load_nonexistent_returns_empty(self):
        pool = PersonaPool(
            pool_path=Path("/tmp/_no_pool_xyz.json"),
            done_keys_path=Path("/tmp/_no_done_xyz.json"),
        )
        assert pool.load() == []

    def test_done_keys_roundtrip(self):
        """save_done_keys → load_done_keys 應完整還原集合。"""
        keys = {("lllll", "police officer"), ("mhmlh", "truck driver")}
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PersonaPool(
                pool_path=Path(tmpdir) / "pool.json",
                done_keys_path=Path(tmpdir) / "done.json",
            )
            pool.save_done_keys(keys)
            assert pool.load_done_keys() == keys

    def test_skips_existing_combos(self):
        """
        done_keys 中已存在的 (ocean_key, occupation) 組合不應再呼叫 generator。
        """
        config = {
            "ocean": {"levels": ["medium"]},
            "occupations": {"enforcement": ["police officer"]},
            "demographic": {"age_groups": ["36-50"], "is_parent": [True]},
            "generation": {"model": "gpt-4o-mini", "n_occupations": None,
                           "random_seed": 0, "max_retries": 0},
        }
        existing_key = (_make_ocean().key(), "police officer")  # ("mmmmm", "police officer")

        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PersonaPool(
                pool_path=Path(tmpdir) / "pool.json",
                done_keys_path=Path(tmpdir) / "done.json",
            )
            pool.save_done_keys({existing_key})

            mock_gen = MagicMock(spec=PersonaGenerator)
            pool.generate_all(mock_gen, config, rng=random.Random(0))

        mock_gen.generate.assert_not_called()

    def test_invalid_persona_not_saved_to_pool(self):
        """
        驗證失敗（is_valid=False）的 persona 不應出現在 persona_pool.json，
        但對應組合應記入 done_keys。
        """
        config = {
            "ocean": {"levels": ["medium"]},
            "occupations": {"general": ["truck driver"]},
            "demographic": {"age_groups": ["36-50"], "is_parent": [True]},
            "generation": {"model": "gpt-4o-mini", "n_occupations": None,
                           "random_seed": 0, "max_retries": 0},
        }
        invalid_payload = json.dumps({"is_valid": False})

        gen = PersonaGenerator(model="gpt-4o-mini", api_key="fake")
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PersonaPool(
                pool_path=Path(tmpdir) / "pool.json",
                done_keys_path=Path(tmpdir) / "done.json",
            )
            with patch.object(gen._client.chat.completions, "create",
                               return_value=_mock_openai_response(invalid_payload)):
                result = pool.generate_all(gen, config, rng=random.Random(0))

            assert result == []
            # done_keys 應有記錄，避免重跑
            done = pool.load_done_keys()
            assert ("mmmmm", "truck driver") in done


# ------------------------------------------------------------------ #
#  PersonaGenerator 測試（mock OpenAI）
# ------------------------------------------------------------------ #

class TestPersonaGenerator:
    def _make_generator(self) -> PersonaGenerator:
        return PersonaGenerator(model="gpt-4o-mini", api_key="fake-key")

    def test_generate_valid_persona(self):
        """LLM 回傳完整 JSON 時應建立 is_valid=True 的 PersonaProfile。"""
        payload = json.dumps({
            "description_en": "A calm and detail-oriented officer.",
            "description_zh": "一位冷靜且注重細節的警察。",
        })
        gen = self._make_generator()
        with patch.object(gen._client.chat.completions, "create",
                          return_value=_mock_openai_response(payload)):
            persona = gen.generate(_make_ocean(), "police officer", _make_demographic())

        assert persona.is_valid is True
        assert "officer" in persona.description_en

    def test_generate_invalid_combo(self):
        """LLM 回傳 {"is_valid": false} 時應建立 is_valid=False 的殼。"""
        payload = json.dumps({"is_valid": False})
        gen = self._make_generator()
        with patch.object(gen._client.chat.completions, "create",
                          return_value=_mock_openai_response(payload)):
            persona = gen.generate(_make_ocean(), "police officer", _make_demographic())

        assert persona.is_valid is False
        assert persona.description_en == ""

    def test_generate_with_feedback_uses_retry_prompt(self):
        """帶入 feedback 時應呼叫含重試提示的 prompt（檢查 API 被呼叫一次）。"""
        payload = json.dumps({
            "description_en": "Fixed description.",
            "description_zh": "修正後的描述。",
        })
        gen = self._make_generator()
        with patch.object(gen._client.chat.completions, "create",
                          return_value=_mock_openai_response(payload)) as mock_create:
            persona = gen.generate(
                _make_ocean(), "police officer", _make_demographic(),
                feedback="Description contradicts low agreeableness.",
                previous_description="Old description.",
            )

        assert persona.is_valid is True
        mock_create.assert_called_once()
        # 確認 user message 含重試關鍵字
        user_content = mock_create.call_args.kwargs["messages"][1]["content"]
        assert "PREVIOUS ATTEMPT" in user_content
        assert "VALIDATOR FEEDBACK" in user_content

    def test_validate_returns_valid_result(self):
        """LLM 回傳 {"verdict": "VALID", "reason": ""} 時應回傳 is_valid=True。"""
        payload = json.dumps({"verdict": "VALID", "reason": ""})
        gen = self._make_generator()
        with patch.object(gen._client.chat.completions, "create",
                          return_value=_mock_openai_response(payload)):
            result = gen.validate(_make_persona())

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.reason == ""

    def test_validate_returns_invalid_result_with_reason(self):
        """LLM 回傳 INVALID 時應回傳 is_valid=False 且帶有 reason。"""
        reason_text = "The extraversion level is too high for the described reserved behavior."
        payload = json.dumps({"verdict": "INVALID", "reason": reason_text})
        gen = self._make_generator()
        with patch.object(gen._client.chat.completions, "create",
                          return_value=_mock_openai_response(payload)):
            result = gen.validate(_make_persona())

        assert result.is_valid is False
        assert result.reason == reason_text

    def test_validate_skips_invalid_persona(self):
        """is_valid=False 的人物不應呼叫 LLM 驗證。"""
        gen = self._make_generator()
        with patch.object(gen._client.chat.completions, "create") as mock_create:
            result = gen.validate(_make_persona(is_valid=False))

        assert result.is_valid is False
        mock_create.assert_not_called()


# ------------------------------------------------------------------ #
#  重試機制測試
# ------------------------------------------------------------------ #

class TestRetryMechanism:
    def test_retry_on_validation_failure(self):
        """
        第一次驗證失敗後，應帶入 reason 重試生成；第二次驗證通過。
        共應呼叫 generate 2 次、validate 2 次。
        """
        gen_payload = json.dumps({
            "description_en": "Some description.",
            "description_zh": "某描述。",
        })
        invalid_validate = json.dumps({
            "verdict": "INVALID",
            "reason": "Description contradicts neuroticism level.",
        })
        valid_validate = json.dumps({"verdict": "VALID", "reason": ""})

        # 呼叫順序：generate → validate(INVALID) → generate → validate(VALID)
        responses = [
            _mock_openai_response(gen_payload),
            _mock_openai_response(invalid_validate),
            _mock_openai_response(gen_payload),
            _mock_openai_response(valid_validate),
        ]

        gen = PersonaGenerator(model="gpt-4o-mini", api_key="fake")
        config = {**_minimal_config(), "generation": {
            **_minimal_config()["generation"], "max_retries": 2
        }}
        config["ocean"]["levels"] = ["medium"]
        config["occupations"] = {"enforcement": ["police officer"]}

        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PersonaPool(
                pool_path=Path(tmpdir) / "pool.json",
                done_keys_path=Path(tmpdir) / "done.json",
            )
            with patch.object(gen._client.chat.completions, "create",
                               side_effect=responses):
                result = pool.generate_all(gen, config, rng=random.Random(0))

        assert len(result) == 1
        assert result[0].is_valid is True

    def test_exhausted_retries_marks_invalid(self):
        """
        重試次數耗盡後，persona 應標記為 is_valid=False 且不存入 pool。
        """
        gen_payload = json.dumps({
            "description_en": "Some description.",
            "description_zh": "某描述。",
        })
        invalid_validate = json.dumps({
            "verdict": "INVALID",
            "reason": "Inconsistency persists.",
        })

        # max_retries=1：generate → validate(fail) → generate → validate(fail) → 放棄
        responses = [
            _mock_openai_response(gen_payload),
            _mock_openai_response(invalid_validate),
            _mock_openai_response(gen_payload),
            _mock_openai_response(invalid_validate),
        ]

        gen = PersonaGenerator(model="gpt-4o-mini", api_key="fake")
        config = {**_minimal_config()}
        config["ocean"]["levels"] = ["medium"]
        config["occupations"] = {"enforcement": ["police officer"]}
        config["generation"]["max_retries"] = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PersonaPool(
                pool_path=Path(tmpdir) / "pool.json",
                done_keys_path=Path(tmpdir) / "done.json",
            )
            with patch.object(gen._client.chat.completions, "create",
                               side_effect=responses):
                result = pool.generate_all(gen, config, rng=random.Random(0))

            # valid pool 應為空；done_keys 應有記錄
            assert result == []
            done = pool.load_done_keys()
            assert ("mmmmm", "police officer") in done

    def test_unrealistic_combo_not_retried(self):
        """
        generate() 回傳 {"is_valid": false} 時（LLM 自評不現實），不應重試。
        API 只被呼叫一次。
        """
        unrealistic_payload = json.dumps({"is_valid": False})

        gen = PersonaGenerator(model="gpt-4o-mini", api_key="fake")
        config = {**_minimal_config()}
        config["ocean"]["levels"] = ["medium"]
        config["occupations"] = {"enforcement": ["police officer"]}
        config["generation"]["max_retries"] = 3  # 設高，但不應重試

        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PersonaPool(
                pool_path=Path(tmpdir) / "pool.json",
                done_keys_path=Path(tmpdir) / "done.json",
            )
            with patch.object(gen._client.chat.completions, "create",
                               return_value=_mock_openai_response(unrealistic_payload)) as mock_create:
                pool.generate_all(gen, config, rng=random.Random(0))

        # 只有一次 generate 呼叫，沒有 validate，沒有重試
        assert mock_create.call_count == 1


# ------------------------------------------------------------------ #
#  PersonaGeneratorFactory 測試
# ------------------------------------------------------------------ #

class TestPersonaGeneratorFactory:
    def test_creates_generator_with_correct_model(self):
        config = {
            "generation": {"model": "gpt-4o", "random_seed": 42, "n_occupations": None}
        }
        with patch.dict("os.environ", {"OPENAI_API_KEY": "fake"}):
            gen = PersonaGeneratorFactory.create_generator(config)

        assert isinstance(gen, PersonaGenerator)
        assert gen._model == "gpt-4o"


# ------------------------------------------------------------------ #
#  端對端生成流程測試
# ------------------------------------------------------------------ #

class TestGenerateAllFlow:
    def test_generate_all_produces_valid_personas(self):
        """
        2^5 OCEAN × 2 職業 = 64 組合，全部通過驗證，pool 應有 64 筆。
        """
        gen_payload = json.dumps({
            "description_en": "Test persona.",
            "description_zh": "測試人物。",
        })
        val_payload = json.dumps({"verdict": "VALID", "reason": ""})

        call_count = 0

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            # 奇數呼叫為 generate，偶數呼叫為 validate
            return _mock_openai_response(gen_payload if call_count % 2 == 1 else val_payload)

        gen = PersonaGenerator(model="gpt-4o-mini", api_key="fake")
        config = _minimal_config()

        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PersonaPool(
                pool_path=Path(tmpdir) / "pool.json",
                done_keys_path=Path(tmpdir) / "done.json",
            )
            with patch.object(gen._client.chat.completions, "create",
                               side_effect=fake_create):
                result = pool.generate_all(gen, config, rng=random.Random(0))

        assert len(result) == 64
        assert all(p.is_valid for p in result)

    def test_generate_all_243_ocean_combos_count(self):
        """3 個 OCEAN 等級 × 5 維度 = 243 個組合。"""
        levels = ["low", "medium", "high"]
        combos = list(itertools.product(levels, repeat=5))
        assert len(combos) == 243
