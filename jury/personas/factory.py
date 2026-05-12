"""
工廠模式：PersonaGeneratorFactory 根據設定檔建立 PersonaGenerator。
"""
from __future__ import annotations

import os

from personas.generator import PersonaGenerator


class PersonaGeneratorFactory:
    """
    工廠模式 (Factory Pattern)
    根據 config dict 建立對應的 PersonaGenerator 實例。
    """

    @staticmethod
    def create_generator(config: dict) -> PersonaGenerator:
        """
        從設定 dict 讀取 model 名稱，並從環境變數讀取 API key。

        Args:
            config: 由 personas.yaml 解析而來的 dict，需含 generation.model 鍵。

        Returns:
            PersonaGenerator 實例。
        """
        model: str = config["generation"]["model"]
        # API key 優先從環境變數讀取，不寫死在設定檔裡
        api_key: str | None = os.getenv("OPENAI_API_KEY")
        return PersonaGenerator(model=model, api_key=api_key)
