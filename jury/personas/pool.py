"""
Persona 池管理，分為兩個職責清楚的 class：

  OceanDescriptionPool — LLM 生成 243 個 OceanDescription，支援斷點續跑
  PersonaPool          — 純組合：OceanDescription × 職業 × Demographic，零 LLM 呼叫

儲存檔案：
  ocean_descriptions.json — 243 筆 valid OceanDescription（LLM 輸出，乾淨）
  ocean_done_keys.json    — 已處理過的 ocean key 字串集合（斷點追蹤，極輕量）
"""
from __future__ import annotations

import itertools
import json
import random
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from personas.generator import PersonaGenerator
from personas.models import Demographic, OceanDescription, OceanProfile, PersonaProfile

_DEFAULT_DESCRIPTIONS_PATH = Path(__file__).parent / "ocean_descriptions.json"
_DEFAULT_DONE_KEYS_PATH     = Path(__file__).parent / "ocean_done_keys.json"


class OceanDescriptionPool:
    """
    外觀模式 (Facade Pattern)
    管理 243 個 OceanDescription 的生成、重試、存檔與斷點續跑。
    """

    def __init__(
        self,
        descriptions_path: Path = _DEFAULT_DESCRIPTIONS_PATH,
        done_keys_path: Path = _DEFAULT_DONE_KEYS_PATH,
    ) -> None:
        self.descriptions_path = descriptions_path
        self.done_keys_path    = done_keys_path

    # ------------------------------------------------------------------ #
    #  載入 / 儲存
    # ------------------------------------------------------------------ #

    def load(self) -> list[OceanDescription]:
        """載入 valid OceanDescription 列表；檔案不存在則回傳空 list。"""
        if not self.descriptions_path.exists():
            return []
        with self.descriptions_path.open("r", encoding="utf-8") as f:
            return [OceanDescription.from_dict(d) for d in json.load(f)]

    def save(self, descriptions: list[OceanDescription]) -> None:
        """將 valid OceanDescription 列表寫入 JSON（完整覆寫）。"""
        self.descriptions_path.parent.mkdir(parents=True, exist_ok=True)
        with self.descriptions_path.open("w", encoding="utf-8") as f:
            json.dump(
                [d.to_dict() for d in descriptions], f, ensure_ascii=False, indent=2
            )

    def load_done_keys(self) -> set[str]:
        """載入已處理的 ocean key 集合；檔案不存在則回傳空 set。"""
        if not self.done_keys_path.exists():
            return set()
        with self.done_keys_path.open("r", encoding="utf-8") as f:
            return set(json.load(f))

    def save_done_keys(self, done_keys: set[str]) -> None:
        """將已處理 ocean key 集合寫入 JSON（完整覆寫）。"""
        self.done_keys_path.parent.mkdir(parents=True, exist_ok=True)
        with self.done_keys_path.open("w", encoding="utf-8") as f:
            json.dump(sorted(done_keys), f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    #  生成
    # ------------------------------------------------------------------ #

    def generate_all(
        self,
        generator: PersonaGenerator,
        config: dict,
        rng: Optional[random.Random] = None,
    ) -> list[OceanDescription]:
        """
        生成全部 243 個 OceanDescription：
        1. 載入 done_keys，跳過已處理的 OCEAN 組合
        2. 對每個未處理的 OceanProfile 呼叫 generate → validate，失敗則重試
        3. LLM 自評無法描述 → 直接記為 done，不重試
        4. 每個 OCEAN combo 完成後立即存檔

        Returns:
            所有 is_valid=True 的 OceanDescription 列表。
        """
        if rng is None:
            rng = random.Random(config["generation"].get("random_seed", 42))

        max_retries: int = config["generation"].get("max_retries", 2)
        levels: list[str] = config["ocean"]["levels"]

        done_keys   = self.load_done_keys()
        valid_descs = self.load()

        for combo in tqdm(
            itertools.product(levels, repeat=5),
            total=len(levels) ** 5,
            desc="Generating OCEAN descriptions",
            unit="combo",
        ):
            ocean = OceanProfile(*combo)
            key   = ocean.key()

            if key in done_keys:
                continue

            desc = self._generate_with_retry(generator, ocean, max_retries)

            if desc.is_valid:
                valid_descs.append(desc)

            done_keys.add(key)
            self.save(valid_descs)
            self.save_done_keys(done_keys)

        return valid_descs

    # ------------------------------------------------------------------ #
    #  內部輔助
    # ------------------------------------------------------------------ #

    @staticmethod
    def _generate_with_retry(
        generator: PersonaGenerator,
        ocean: OceanProfile,
        max_retries: int,
    ) -> OceanDescription:
        """
        帶重試的生成流程：
        - generate → validate；失敗則把 reason 注入 prompt 重試。
        - LLM 自評無法描述（is_valid=False）→ 立即停止，不重試。
        """
        feedback: str | None             = None
        previous_description: str | None = None

        for _ in range(max_retries + 1):
            desc = generator.generate(ocean, feedback=feedback,
                                      previous_description=previous_description)

            if not desc.is_valid:
                return desc  # LLM 自評無法描述，不重試

            result = generator.validate(desc)
            if result.is_valid:
                return desc

            # 帶入失敗原因供下一輪重試
            feedback             = result.reason
            previous_description = desc.description_en

        desc.is_valid = False
        return desc


class PersonaPool:
    """
    純組合器 (Builder Pattern)
    將 OceanDescription 與職業、Demographic 組合成 PersonaProfile，無任何 LLM 呼叫。
    PersonaProfile 可由 ocean_descriptions.json + config 完全決定性地重建，
    因此不需要獨立持久化。
    """

    def build(
        self,
        descriptions: list[OceanDescription],
        config: dict,
        rng: random.Random,
    ) -> list[PersonaProfile]:
        """
        對每個 OceanDescription 搭配 N 個職業，各自 random sample 一個 Demographic。

        Args:
            descriptions: valid OceanDescription 列表（來自 OceanDescriptionPool）。
            config:        personas.yaml 解析後的 dict。
            rng:           已設定 seed 的 random.Random 實例，確保可重現。

        Returns:
            PersonaProfile 列表（len = len(descriptions) × n_occupations_per_desc）。
        """
        all_occupations: list[str] = [
            occ for occs in config["occupations"].values() for occ in occs
        ]
        n_occupations: Optional[int] = config["generation"].get("n_occupations")
        age_groups: list[str]        = config["demographic"]["age_groups"]
        is_parent_options: list[bool] = config["demographic"]["is_parent"]

        personas: list[PersonaProfile] = []

        for desc in descriptions:
            occupations = (
                rng.sample(all_occupations, n_occupations)
                if n_occupations and n_occupations < len(all_occupations)
                else list(all_occupations)
            )

            for occ in occupations:
                demographic = Demographic(
                    age_group=rng.choice(age_groups),
                    is_parent=rng.choice(is_parent_options),
                )
                personas.append(PersonaProfile(
                    ocean_description=desc,
                    occupation=occ,
                    demographic=demographic,
                ))

        return personas
