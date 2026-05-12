"""
LLM Prompt 模板。

設計原則：生成 prompt 刻意不傳入職業資訊，確保 OCEAN 描述是純人格行為描述，
可與任意職業 concat 而不產生 stereotype 污染。
所有英文 prompt 字串旁均附有中文翻譯的行內或 block 註解。
"""
from __future__ import annotations

from personas.models import OceanDescription, OceanProfile

# OCEAN 各維度各等級的行為描述詞（用於組裝 prompt 時描述人格特質）
# Behavioral descriptors for each OCEAN dimension level (used in prompt construction)
OCEAN_DESCRIPTORS: dict[str, dict[str, str]] = {
    "openness": {
        # 開放性
        "low":    "conventional, prefers routine and familiar approaches, resistant to new ideas",
        # 低：傳統保守、偏好例行慣例、對新想法有抗拒
        "medium": "moderately curious, open to some new experiences while valuing stability",
        # 中：適度好奇、部分接受新體驗但重視穩定
        "high":   "highly creative, intellectually curious, embraces novel perspectives eagerly",
        # 高：富創意、求知欲強、積極擁抱新觀點
    },
    "conscientiousness": {
        # 盡責性
        "low":    "spontaneous, flexible, often disorganized and may miss deadlines",
        # 低：衝動隨興、缺乏組織、容易錯過截止日期
        "medium": "moderately organized, balances structure with flexibility",
        # 中：適度有組織、在結構與彈性間取得平衡
        "high":   "highly disciplined, meticulous, detail-oriented, plans everything carefully",
        # 高：紀律嚴明、細心謹慎、凡事謹慎規劃
    },
    "extraversion": {
        # 外向性
        "low":    "introverted, reserved, prefers solitary activities and small groups",
        # 低：內向、含蓄、偏好獨處或小群體
        "medium": "ambivert, comfortable in both social and solitary settings",
        # 中：社交與獨處皆自在
        "high":   "highly outgoing, energetic, thrives in social settings, talks freely",
        # 高：非常外向、活力充沛、享受社交、言談自由
    },
    "agreeableness": {
        # 親和性
        "low":    "competitive, skeptical of others' motives, prioritizes personal goals",
        # 低：競爭心強、對他人動機持懷疑態度、優先考慮個人目標
        "medium": "generally cooperative but will assert own views when needed",
        # 中：通常合作，必要時會堅持己見
        "high":   "deeply empathetic, cooperative, avoids conflict, prioritizes group harmony",
        # 高：富同理心、合作導向、避免衝突、重視群體和諧
    },
    "neuroticism": {
        # 神經質
        "low":    "emotionally stable, calm under pressure, resilient to stress",
        # 低：情緒穩定、壓力下保持冷靜、抗壓性強
        "medium": "moderate emotional reactivity, occasionally stressed but generally manages well",
        # 中：情緒反應適中、偶有壓力但通常能妥善應對
        "high":   "prone to anxiety and stress, emotionally reactive, may ruminate on problems",
        # 高：容易焦慮與緊張、情緒反應強烈、傾向反覆思考問題
    },
}


def build_generation_system_prompt() -> str:
    """
    建立 LLM 呼叫一（生成 OCEAN 純人格描述）的 system prompt。
    明確要求 LLM 不得提及任何職業，確保描述可跨職業通用。
    """
    # 英文 System Prompt：角色設定為人格研究員，強調描述必須職業中立
    # English: Sets LLM role as a personality researcher; enforces occupation-neutral descriptions
    return (
        "You are a personality researcher writing behavioral profiles for social science simulations. "
        # 你是社會科學模擬研究的人格研究員
        "Given an OCEAN personality profile, write a behavioral description of this person. "
        # 根據 OCEAN 人格剖析，撰寫此人的行為描述
        "\n\n"
        "CRITICAL RULE: Do NOT mention any specific occupation, job title, or professional role. "
        # 關鍵規則：絕對不得提及任何職業、職稱或專業角色
        "The description must apply equally well to a nurse, a lawyer, a truck driver, or any other profession. "
        # 描述必須同樣適用於護理師、律師、卡車司機或任何其他職業
        "\n\n"
        "Cover these three aspects:\n"
        # 涵蓋以下三個面向
        "  1. Specific behavioral habits (2-3 items)\n"
        # 1. 具體行為習慣（2-3 個）
        "  2. Typical reaction pattern when facing moral dilemmas\n"
        # 2. 面對道德困境時的典型反應模式
        "  3. Speaking style in group discussions\n"
        # 3. 在群體討論中的發言風格
        "\n"
        "Output a JSON object with exactly these fields:\n"
        # 輸出含以下欄位的 JSON 物件
        '  "description_en": the behavioral description in English (3-5 sentences)\n'
        # description_en：英文行為描述（3-5 句）
        '  "description_zh": a direct Chinese translation of description_en\n'
        # description_zh：description_en 的直接中文翻譯
        "\n"
        'If the OCEAN combination is internally contradictory and cannot be described coherently, '
        # 若 OCEAN 組合在內部邏輯上自相矛盾而無法合理描述
        'output ONLY: {"is_valid": false}'
        # 則只輸出：{"is_valid": false}
    )


def build_generation_user_prompt(ocean: OceanProfile) -> str:
    """
    建立 LLM 呼叫一的 user prompt。
    只傳入 OCEAN 等級，不含職業或人口統計（設計上刻意排除）。
    """
    # 組裝各維度的具體描述詞
    ocean_lines = "\n".join(
        f"  - {dim.capitalize()} ({getattr(ocean, dim)}): "
        f"{OCEAN_DESCRIPTORS[dim][getattr(ocean, dim)]}"
        for dim in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism")
    )

    # 英文 User Prompt：只提供 OCEAN 剖析，要求生成職業中立的行為描述
    # English: Provides only the OCEAN profile; occupation is intentionally excluded
    return (
        "Generate an occupation-neutral behavioral description for a person with this OCEAN profile:\n\n"
        # 請為以下 OCEAN 剖析生成一個不涉及職業的行為描述
        f"OCEAN PERSONALITY PROFILE:\n{ocean_lines}\n\n"
        # OCEAN 人格剖析
        "Remember: output JSON only. "
        # 注意：只輸出 JSON
        "Do NOT mention any job, profession, or workplace context. "
        # 不得提及任何工作、職業或職場情境
        'If the combination cannot be described coherently, output {"is_valid": false} only.'
        # 若組合無法合理描述，只輸出 {"is_valid": false}
    )


def build_validation_system_prompt() -> str:
    """
    建立 LLM 呼叫二（驗證 OCEAN 描述）的 system prompt。
    同時檢查：內部一致性、職業中立性（不得有職業相關語言）。
    """
    # 英文 System Prompt：驗證描述的一致性與職業中立性
    # English: Validates both consistency with OCEAN profile and occupation-neutrality
    return (
        "You are a quality reviewer for personality descriptions used in social science simulations. "
        # 你是社會科學模擬人格描述的品質審核員
        "Evaluate the given description against two criteria:\n"
        # 根據以下兩個標準評估描述
        "  1. OCEAN consistency: does the behavior match the stated personality levels?\n"
        # 1. OCEAN 一致性：行為是否符合人格維度等級？
        "  2. Occupation neutrality: does the description avoid mentioning any specific job or profession?\n"
        # 2. 職業中立性：描述是否完全沒有提及任何職業？
        "\n"
        "Output a JSON object with exactly two fields:\n"
        # 輸出含以下兩個欄位的 JSON 物件
        '  "verdict": "VALID" or "INVALID"\n'
        '  "reason": empty string if VALID; '
        # 若通過則為空字串
        "otherwise a concise 1-2 sentence explanation of exactly what fails."
        # 若失敗則以 1-2 句說明具體哪裡不符合標準
    )


def build_validation_user_prompt(ocean: OceanProfile, description_en: str) -> str:
    """
    建立 LLM 呼叫二的 user prompt。
    只傳入 OCEAN profile + 描述；不含職業（職業不應出現在描述中）。
    """
    # 英文 User Prompt：提供 OCEAN 剖析與描述供驗證
    # English: Provides the OCEAN profile and description for validation
    return (
        "Please validate the following personality description:\n\n"
        # 請驗證以下人格描述
        f"OPENNESS: {ocean.openness}\n"
        f"CONSCIENTIOUSNESS: {ocean.conscientiousness}\n"
        f"EXTRAVERSION: {ocean.extraversion}\n"
        f"AGREEABLENESS: {ocean.agreeableness}\n"
        f"NEUROTICISM: {ocean.neuroticism}\n\n"
        f"DESCRIPTION:\n{description_en}\n\n"
        # 描述
        'Respond with {"verdict": "VALID", "reason": ""} or '
        # 通過：{"verdict": "VALID", "reason": ""}
        '{"verdict": "INVALID", "reason": "<specific issue>"}.'
        # 失敗：{"verdict": "INVALID", "reason": "具體問題"}
    )


def build_retry_generation_user_prompt(
    ocean: OceanProfile,
    previous_description: str,
    feedback: str,
) -> str:
    """
    建立重新生成的 user prompt。
    帶入上次失敗的描述與驗證器的具體回饋，引導 LLM 針對問題修正。
    職業資訊同樣刻意排除。
    """
    base = build_generation_user_prompt(ocean)
    # 英文：在原始 prompt 後附加失敗描述與驗證器回饋
    # English: Appends the rejected description and validator feedback to the base prompt
    return (
        f"{base}\n\n"
        "--- PREVIOUS ATTEMPT (rejected by validator) ---\n"
        # 上次生成的描述（已被驗證器拒絕）
        f"{previous_description}\n\n"
        "--- VALIDATOR FEEDBACK ---\n"
        # 驗證器的具體反饋
        f"{feedback}\n\n"
        "Please address the feedback and regenerate. "
        # 請根據反饋修正並重新生成
        "Output JSON with description_en and description_zh only. "
        # 只輸出 description_en 和 description_zh
        "Still no occupation mentions."
        # 仍然不得提及任何職業
    )
