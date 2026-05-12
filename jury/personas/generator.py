"""
LLM 呼叫封裝：PersonaGenerator 負責生成與驗證 OceanDescription。
職業與人口統計由 PersonaPool 在 LLM 呼叫之外處理。
"""
from __future__ import annotations

import json

import openai

from personas.models import OceanDescription, OceanProfile, ValidationResult
from personas.prompts import (
    build_generation_system_prompt,
    build_generation_user_prompt,
    build_retry_generation_user_prompt,
    build_validation_system_prompt,
    build_validation_user_prompt,
)

_JSON_RESPONSE_FORMAT = {"type": "json_object"}


class PersonaGenerator:
    """
    封裝兩次 LLM 呼叫：
    - generate()：給定 OceanProfile，產出純人格行為描述（OceanDescription）
    - validate()：驗證描述的 OCEAN 一致性與職業中立性，回傳 ValidationResult
    """

    def __init__(self, model: str, api_key: str | None = None) -> None:
        """
        api_key 若為 None，則由環境變數 OPENAI_API_KEY 自動讀取。
        """
        self._model = model
        self._client = openai.OpenAI(api_key=api_key)

    def generate(
        self,
        ocean: OceanProfile,
        feedback: str | None = None,
        previous_description: str | None = None,
    ) -> OceanDescription:
        """
        LLM 呼叫一：根據 OceanProfile 生成純人格行為描述。

        Args:
            feedback: 驗證器回傳的失敗原因（重試時傳入）。
            previous_description: 上次被拒絕的英文描述（重試時傳入）。

        Returns:
            OceanDescription；若 LLM 判定組合無法合理描述，is_valid=False。
        """
        system_msg = build_generation_system_prompt()

        if feedback and previous_description:
            user_msg = build_retry_generation_user_prompt(ocean, previous_description, feedback)
        else:
            user_msg = build_generation_user_prompt(ocean)

        raw = self._chat(system_msg, user_msg)
        data = json.loads(raw)

        if data.get("is_valid") is False:
            return OceanDescription(
                ocean=ocean, description_en="", description_zh="", is_valid=False
            )

        return OceanDescription(
            ocean=ocean,
            description_en=data.get("description_en", ""),
            description_zh=data.get("description_zh", ""),
            is_valid=True,
        )

    def validate(self, desc: OceanDescription) -> ValidationResult:
        """
        LLM 呼叫二：驗證 OceanDescription 的 OCEAN 一致性與職業中立性。

        Returns:
            ValidationResult：包含 is_valid 旗標與失敗原因。
        """
        if not desc.is_valid:
            return ValidationResult(
                is_valid=False, reason="Description marked invalid during generation."
            )

        system_msg = build_validation_system_prompt()
        user_msg = build_validation_user_prompt(desc.ocean, desc.description_en)

        raw = self._chat(system_msg, user_msg)
        data = json.loads(raw)

        is_valid = data.get("verdict", "INVALID").upper() == "VALID"
        return ValidationResult(is_valid=is_valid, reason=data.get("reason", ""))

    def _chat(self, system_msg: str, user_msg: str) -> str:
        """發送 chat completion 請求，回傳 content 字串。"""
        response = self._client.chat.completions.create(
            model=self._model,
            response_format=_JSON_RESPONSE_FORMAT,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )
        return response.choices[0].message.content
