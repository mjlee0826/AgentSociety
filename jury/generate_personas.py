"""
Phase 1 執行入口：生成 Persona 池並匯出結果。

執行流程：
  1. 載入 config/personas.yaml
  2. 透過 PersonaGeneratorFactory 建立 PersonaGenerator
  3. OceanDescriptionPool.generate_all() 生成 243 個 OCEAN 純人格描述（支援斷點續跑）
  4. PersonaPool.build() 組合職業 × Demographic，零 LLM 呼叫
  5. 將完整 PersonaProfile 列表匯出至 personas_output.json

用法：
  cd jury
  python generate_personas.py
  python generate_personas.py --config config/personas.yaml --output personas_output.json
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import yaml

from personas.factory import PersonaGeneratorFactory
from personas.pool import OceanDescriptionPool, PersonaPool

# 預設路徑
_DEFAULT_CONFIG = Path(__file__).parent / "config" / "personas.yaml"
_DEFAULT_OUTPUT = Path(__file__).parent / "personas_output.json"


def load_config(config_path: Path) -> dict:
    """載入並回傳 personas.yaml 設定 dict。"""
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(config_path: Path, output_path: Path) -> None:
    """
    執行完整的 Persona 池生成流程。

    Args:
        config_path: personas.yaml 的路徑。
        output_path: 輸出 JSON 的路徑。
    """
    config = load_config(config_path)
    seed: int = config["generation"].get("random_seed", 42)
    rng = random.Random(seed)

    # Phase 1a：生成 243 個 OCEAN 純人格描述（LLM，支援斷點續跑）
    generator = PersonaGeneratorFactory.create_generator(config)
    desc_pool = OceanDescriptionPool()
    descriptions = desc_pool.generate_all(generator, config, rng=random.Random(seed))

    valid_count = len(descriptions)
    print(f"Valid OCEAN descriptions: {valid_count} / 243")

    # Phase 1b：組合職業 × Demographic，產出 PersonaProfile 列表（無 LLM）
    persona_pool = PersonaPool()
    personas = persona_pool.build(descriptions, config, rng=rng)

    print(f"Total PersonaProfiles built: {len(personas)}")

    # 匯出完整 PersonaProfile 列表
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in personas], f, ensure_ascii=False, indent=2)

    print(f"Output written to: {output_path}")


def main() -> None:
    """CLI 入口：解析引數並執行生成流程。"""
    parser = argparse.ArgumentParser(
        description="Phase 1: Generate the full Persona pool (OCEAN × occupation × demographic)."
        # Phase 1：生成完整的 Persona 池（OCEAN × 職業 × 人口統計）
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_CONFIG,
        help=f"Path to personas.yaml (default: {_DEFAULT_CONFIG})",
        # personas.yaml 路徑（預設值如上）
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {_DEFAULT_OUTPUT})",
        # 輸出 JSON 路徑（預設值如上）
    )
    args = parser.parse_args()
    run(config_path=args.config, output_path=args.output)


if __name__ == "__main__":
    main()
