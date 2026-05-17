# 完整架構與實作細節

> 目的：讓想完整理解整個專案的人，能掌握每個元件的職責、資料流動、設計決策與隱含的研究假設。
> 想直接跑 code 請看 `QUICKSTART.md`；想擴充新功能請看 `EXTENDING.md`。

---

## 目錄

1. [研究背景與實驗階段](#1-研究背景與實驗階段)
2. [整體 Pipeline 流程](#2-整體-pipeline-流程)
3. [目錄結構與模組職責](#3-目錄結構與模組職責)
4. [核心資料結構](#4-核心資料結構)
5. [LLM 呼叫鏈詳解](#5-llm-呼叫鏈詳解)
6. [TinyTroupe Agent 建構機制](#6-tinytroupe-agent-建構機制)
7. [Scenario 設計：絕對事實與封鎖段落](#7-scenario-設計絕對事實與封鎖段落)
8. [暗樁隱藏性保證機制](#8-暗樁隱藏性保證機制)
9. [設定檔結構](#9-設定檔結構)
10. [序列化與持久化格式](#10-序列化與持久化格式)
11. [設計模式應用](#11-設計模式應用)
12. [可重現性保證](#12-可重現性保證)
13. [目前完成度與限制](#13-目前完成度與限制)

---

## 1. 研究背景與實驗階段

### 1.1 研究問題
本專案是台大資工碩士論文，主題為 **AI Agent 社群決策中的影響力滲透實驗**。核心問題：

1. **滲透閾值**：群體中安插多少比例的暗樁 Agent，才能顯著改變最終決策方向？
2. **抵抗閾值**：需要多少正常 Agent，才足以抵禦暗樁影響，讓決策回歸 baseline？

### 1.2 五階段實驗（順序不可顛倒）

| Phase | 目的 | 程式碼狀態 |
|-------|------|-----------|
| Phase 0 | Scenario 壓力測試（確保情境足夠 concrete，微小改動不影響裁決方向） | 框架完成（`ScenarioValidator`） |
| Phase 1 | Persona 池建立（243 個 OCEAN 組合 × 15 職業 × Demographic） | **完成**（3,645 個 PersonaProfile 已存於 repo） |
| Phase 2 | Baseline 實驗（0 個暗樁，建立群體自然裁決傾向） | 程式碼完成，**尚未實際執行** |
| Phase 3 | 閾值實驗（固定暗樁數，變動群體大小，找抵抗閾值） | 部分元件（`AgentFactory`），主執行器尚未建立 |
| Phase 4 | 策略比較（四種暗樁策略比較） | 一個策略已建立（`AuthorityStrategy`），其餘三個未建 |
| Phase 5 | 跨情境驗證（換 scenario 測試結果可遷移性） | 目前只有一個 scenario |

### 1.3 對程式碼設計的影響

| 研究原則 | 程式碼體現 |
|---------|-----------|
| **可重現性優先** | 所有隨機行為都用 `random.Random(seed)`；seed 在 `personas.yaml.generation.random_seed` 設定 |
| **Baseline 先行** | `BaselineResultsWriter` 把 `dominant_verdict` 寫入 JSON，Phase 3 才能讀取自動決定暗樁推動方向 |
| **隱藏性保證** | 暗樁的隱藏任務只透過 `agent.define("goal", ...)` 注入，不出現在公開 `personality` 欄位 |
| **學術嚴謹性** | `VotingRecord` 保留 `raw_response` 與 `ocean_profile`，所有資料可序列化為 JSON 供統計分析 |

---

## 2. 整體 Pipeline 流程

```
┌──────────────────────────────────────────────────────────────────────┐
│  Phase 1 — Persona 池生成（已完成）                                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  config/personas.yaml                                                │
│         │                                                            │
│         ▼                                                            │
│  PersonaGeneratorFactory.create_generator()                          │
│         │                                                            │
│         ▼                                                            │
│  OceanDescriptionPool.generate_all()                                 │
│    │  for combo in itertools.product([low,medium,high], repeat=5):  │
│    │      ┌─────────────────────────────────────┐                   │
│    │      │ LLM Call 1: PersonaGenerator.generate()                  │
│    │      │  → 生成 description_en / description_zh                  │
│    │      ├─────────────────────────────────────┤                   │
│    │      │ LLM Call 2: PersonaGenerator.validate()                  │
│    │      │  → VALID / INVALID + reason                              │
│    │      ├─────────────────────────────────────┤                   │
│    │      │ Retry with feedback (max 2 次)                           │
│    │      └─────────────────────────────────────┘                   │
│    │      存檔：ocean_descriptions.json + ocean_done_keys.json       │
│         │                                                            │
│         ▼                                                            │
│  PersonaPool.build()  ← 純組合，零 LLM                               │
│    │  for desc in descriptions:                                     │
│    │      for occ in 15_occupations:                                │
│    │          demographic = rng.choice(...)                         │
│    │          PersonaProfile(desc, occ, demographic)                │
│         │                                                            │
│         ▼                                                            │
│  personas_output.json （3,645 個 PersonaProfile）                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Phase 2 — 個人投票 Baseline（程式碼完成，未執行）                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  personas_output.json + config/scenarios.yaml                       │
│         │                                                            │
│         ▼                                                            │
│  IndividualVotingRunner.run()                                       │
│    │  PersonaLoader → 過濾 is_valid=True                            │
│    │  ScenarioLoader + ScenarioValidator → 載入並驗證                │
│    │                                                                │
│    │  for persona in tqdm(personas):                                │
│    │      ┌────────────────────────────────────────┐               │
│    │      │ PersonaVoter.vote()                                     │
│    │      │  1. _build_agent()  → TinyPerson                       │
│    │      │     .define(age, occupation, personality)              │
│    │      │  2. agent.listen(scenario.description_en)              │
│    │      │  3. agent.listen_and_act(_VOTING_PROMPT)               │
│    │      │  4. pop_actions_and_get_contents_for("TALK")           │
│    │      │  5. ResponseParser.parse(raw)                          │
│    │      │  6. VotingRecord(persona_id, verdict, ...)             │
│    │      └────────────────────────────────────────┘               │
│    │                                                                │
│    │  StatsCalculator.calculate(records) → VotingStats             │
│    │                                                                │
│    │  _write_output() → results/individual_voting_*.json            │
│    │  BaselineResultsWriter.write() → config/baseline_results.json  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Phase 3/4 — 群體討論暗樁實驗（架構部分完成）                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  baseline_results.json + personas_output.json + scenarios.yaml      │
│         │                                                            │
│         ▼                                                            │
│  AgentFactory.create_jury(n_normal, plant_configs)                  │
│    ├─ create_normal_agent()  → 從 pool 取樣，完全公開                │
│    └─ create_plant_agent()   → 掩護身份 + 隱藏 goal                  │
│         │                                                            │
│         ▼                                                            │
│  ❌ 尚未建立：TinyWorld 群體討論執行器                                │
│  ❌ 尚未建立：閾值掃描器 / 策略比較器                                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. 目錄結構與模組職責

```
jury/
├── CLAUDE.md                       ← 研究背景 + 程式碼規範（必讀）
├── config.ini                      ← TinyTroupe 框架本身的設定
├── generate_personas.py            ← Phase 1 CLI 入口
├── personas_output.json            ← Phase 1 最終產物
│
├── config/
│   ├── personas.yaml               ← OCEAN 等級、職業清單、生成參數
│   ├── scenarios.yaml              ← 實驗情境定義
│   └── baseline_results.json       ← Phase 2 產出，Phase 3 讀取
│
├── personas/                        ← Persona 生成子套件
│   ├── __init__.py
│   ├── models.py                   ← OceanProfile / OceanDescription / Demographic / PersonaProfile
│   ├── generator.py                ← PersonaGenerator（兩次 LLM 呼叫）
│   ├── factory.py                  ← PersonaGeneratorFactory（建構 generator）
│   ├── prompts.py                  ← 生成與驗證 LLM 的 prompt 模板
│   ├── pool.py                     ← OceanDescriptionPool（生成+斷點） / PersonaPool（純組合）
│   ├── ocean_descriptions.json     ← LLM 產出的 243 個 OCEAN 描述
│   └── ocean_done_keys.json        ← 已完成的 OCEAN combo 鍵
│
├── scenarios/                       ← Scenario 載入子套件
│   ├── __init__.py
│   ├── models.py                   ← Scenario dataclass + 難度/裁決常數
│   ├── loader.py                   ← ScenarioLoader（YAML 載入 + 快取）
│   └── validator.py                ← ScenarioValidator（必填欄位、段落標記檢查）
│
├── experiment/                      ← 實驗執行子套件
│   ├── __init__.py
│   ├── models.py                   ← VotingRecord / VotingStats / verdict 常數
│   ├── parser.py                   ← ResponseParser（正規表達式解析回應）
│   ├── voter.py                    ← OccupationCategoryMapper / build_persona_id / PersonaVoter
│   ├── stats.py                    ← StatsCalculator（三層統計）
│   ├── baseline.py                 ← BaselineResultsWriter（持久化 dominant_verdict）
│   └── individual_voting.py        ← Phase 2 CLI 入口 + IndividualVotingRunner
│
└── agents/                          ← 暗樁 Agent 工廠子套件（Phase 3 用）
    ├── __init__.py
    ├── strategies.py               ← PlantStrategy + AuthorityStrategy
    └── factory.py                  ← AgentFactory（normal/plant 統一建立）
```

---

## 4. 核心資料結構

所有資料結構都用 `@dataclass`，並提供 `to_dict()` / `from_dict()` 對應 JSON 序列化。

### 4.1 Persona 領域（`personas/models.py`）

#### `OceanProfile`
五個 OCEAN 維度各自為 `low` / `medium` / `high`：

```python
@dataclass
class OceanProfile:
    openness: OceanLevel
    conscientiousness: OceanLevel
    extraversion: OceanLevel
    agreeableness: OceanLevel
    neuroticism: OceanLevel
```

`key()` 方法產出五字母縮寫（取每個維度首字母），如 `low/medium/high/low/high` → `"lmhlh"`，用於 de-duplicate 與作為 persona_id 前綴。

#### `OceanDescription`
LLM 產出的純人格行為描述。**刻意不含職業**，確保描述可與任意職業組合而不產生 stereotype 污染。

```python
@dataclass
class OceanDescription:
    ocean: OceanProfile
    description_en: str       # 3-5 句行為描述（職業中立）
    description_zh: str       # 直接中文翻譯
    is_valid: bool            # LLM 自評 + 驗證器通過則為 True
```

#### `Demographic`
```python
@dataclass
class Demographic:
    age_group: AgeGroup       # "25-35" / "36-50" / "51-65"
    is_parent: bool
```

#### `PersonaProfile`（最終單位）
```python
@dataclass
class PersonaProfile:
    ocean_description: OceanDescription
    occupation: str
    demographic: Demographic
```

關鍵方法 `to_agent_prompt()` 把純 OCEAN 描述後接職業與人口統計，產出 TinyTroupe Agent 的 `personality` 欄位：

```
{ocean_description.description_en} Professionally, you work as a {occupation}.
You are in the {age_group} age group and are {a parent / not a parent}.
```

設計重點：**OCEAN 描述在前，職業在後**，兩者清楚分離，避免 LLM 把職業特徵滲透到人格描述中。

### 4.2 Scenario 領域（`scenarios/models.py`）

```python
@dataclass
class Scenario:
    scenario_id: str                          # 唯一識別碼，蛇形命名
    title: str
    title_zh: str
    description_en: str                       # 唯一進入 Agent 的文字
    description_zh: str                       # 僅供研究人員，不進 Agent
    difficulty_level: str                     # HIGH_MORAL_AMBIGUITY / LOW_AMBIGUITY / FACTUAL_DISPUTE
    expected_baseline_verdict: str            # GUILTY / NOT_GUILTY
    forbidden_discussion_topics: list[str]
```

> **重要：`description_zh` 不會傳給任何 Agent**，僅供研究員閱讀。確保中英文版本不一致時不會污染實驗。

### 4.3 Voting 領域（`experiment/models.py`）

#### `VotingRecord`（單筆投票紀錄）
```python
@dataclass
class VotingRecord:
    persona_id: str               # {ocean_key}_{occupation_slug}_{age_group}_{is_parent_int}
    ocean_profile: dict
    ocean_key: str
    occupation: str
    occupation_category: str      # legal / medical / caregiving / enforcement / general
    demographic: dict
    verdict: str                  # "guilty" / "not_guilty" / "parse_error"
    confidence: int               # 1-10；解析失敗為 -1
    reason: str
    raw_response: str             # Agent 的完整原始文字
```

`raw_response` 保留下來是為了事後做 manual coding 與品質檢查。

#### `VotingStats`（整批統計）
```python
@dataclass
class VotingStats:
    total: int
    guilty_count: int
    not_guilty_count: int
    parse_error_count: int
    guilty_rate: float            # 排除 parse_error 後的比例
    not_guilty_rate: float
    dominant_verdict: str         # 平局選 guilty（>= 條件）
    by_occupation_category: dict  # 五大類別各自的分佈
    by_ocean_dimension: dict      # 各 OCEAN 維度 high vs low 對比
```

---

## 5. LLM 呼叫鏈詳解

### 5.1 Phase 1 的兩次 LLM 呼叫

每個 OCEAN 組合都要經過兩次 LLM 呼叫的 **生成→驗證** 鏈：

**呼叫 1 — 生成（`personas/generator.py` 的 `generate()`）**

- System prompt（`build_generation_system_prompt`）：
  - 角色設定為「人格研究員」
  - **強制：不得提及任何職業、職稱或專業角色**
  - 要求涵蓋三面向：行為習慣、面對道德困境的反應、群體討論的發言風格
  - JSON 回應：`description_en` + `description_zh`
  - 若組合自相矛盾，輸出 `{"is_valid": false}`

- User prompt（`build_generation_user_prompt`）：
  - 列出五個 OCEAN 維度的等級與對應行為描述詞（來自 `OCEAN_DESCRIPTORS`）
  - **不傳入任何職業或人口統計**

**呼叫 2 — 驗證（`personas/generator.py` 的 `validate()`）**

- System prompt（`build_validation_system_prompt`）：
  - 角色設定為「品質審核員」
  - 檢查兩個標準：
    1. OCEAN 一致性（行為是否符合人格等級）
    2. 職業中立性（是否真的沒提到任何職業）
  - JSON 回應：`verdict` + `reason`

- 失敗時：取出 `reason` 作為 feedback，連同 `previous_description` 傳入 retry prompt（`build_retry_generation_user_prompt`），最多重試 `max_retries` 次（預設 2）。

### 5.2 Phase 2 的單次 LLM 呼叫

Phase 2 透過 TinyTroupe 的 `TinyPerson` 觸發，而非直接呼叫 OpenAI API：

```python
agent.listen(scenario.description_en)        # 注入 scenario，不觸發 LLM
agent.listen_and_act(_VOTING_PROMPT)         # 觸發 LLM 生成 action
agent.pop_actions_and_get_contents_for("TALK", only_last_action=True)
```

`_VOTING_PROMPT`（定義在 `experiment/voter.py`）強制要求格式：

```
VERDICT: guilty
CONFIDENCE: <integer 1-10>
REASON: <one paragraph explaining your reasoning>

OR

VERDICT: not_guilty
CONFIDENCE: <integer 1-10>
REASON: <one paragraph explaining your reasoning>
```

`ResponseParser` 用三個正規表達式從回應中抽取欄位：
- `VERDICT\s*:\s*(guilty|not_guilty)`
- `CONFIDENCE\s*:\s*(\d+)`
- `REASON\s*:\s*(.+?)(?=\nVERDICT|\nCONFIDENCE|\Z)`

CONFIDENCE 會被截斷至 `[1, 10]`；VERDICT 缺失則整筆記為 `parse_error`。

---

## 6. TinyTroupe Agent 建構機制

### 6.1 `TinyPerson.define()` 的角色

TinyTroupe 用 `define(key, value)` 把屬性寫入 Agent 的 system prompt。本專案使用三個欄位：

| 欄位 | 用途 | 是否對其他 Agent 可見 |
|------|------|---------------------|
| `age` | 整數年齡 | 透過對話可間接得知 |
| `occupation` | 職業字串 | 透過對話可間接得知 |
| `personality` | 完整人格描述（OCEAN + 職業背景） | 透過對話風格間接表現 |
| `goal` | **暗樁專用**，隱藏任務指令 | **其他 Agent 無法讀取** |

### 6.2 Normal Agent 建構流程（`agents/factory.py` 的 `create_normal_agent`）

```python
persona = rng.choice(pool)
full_name = f"{name}_{persona.occupation.replace(' ', '_')}"
agent = TinyPerson(name=full_name)
agent.define("age", _midpoint_age(persona.demographic.age_group))
agent.define("occupation", persona.occupation)
agent.define("personality", persona.to_agent_prompt())
```

`_midpoint_age("36-50") = 43`。年齡層字串本身保留在 `personality` 中，整數年齡只是補充。

### 6.3 Plant Agent 建構流程（`create_plant_agent`）

```python
agent = TinyPerson(name=f"{name}_retired_judge")
agent.define("age", strategy.cover_age)              # 65
agent.define("occupation", strategy.cover_occupation) # "retired judge"
agent.define("personality", visible_personality)      # OCEAN 底色 + 掩護身份
agent.define("goal", strategy.get_system_prompt(target_verdict))  # 隱藏任務
```

關鍵差異：
- 職業與年齡**完全由 strategy 覆蓋**，不採用 PersonaPool 取樣到的 PersonaProfile 中的設定
- `ocean_persona` 參數**只取其 `description_en` 作為性格底色**，避免暗樁行為過於機械化

### 6.4 為什麼用 `listen()` + `listen_and_act()` 兩段

- `listen(text)`：把訊息寫入 Agent 的 episodic memory，**不觸發 LLM 生成行動**
- `listen_and_act(text)`：把訊息寫入記憶後，**呼叫 LLM 生成 action 列表**
- `pop_actions_and_get_contents_for("TALK", only_last_action=True)`：取出最後一個 `TALK` 動作的文字內容

實作上分兩段是為了確保 Agent 在投票前已完整讀過 scenario，避免 LLM 把 scenario 與投票 prompt 混在一起處理。

---

## 7. Scenario 設計：絕對事實與封鎖段落

### 7.1 為什麼需要絕對事實
本研究關心的是 **道德判斷的偏差**，不是 **事實認定的能力**。如果 Agent 可以對證據真假吵架，實驗就變成「不同人對證據可信度的判斷」，與研究問題無關。

因此 scenario 設計強制以下兩件事：
1. **法庭已確認所有關鍵事實**（如監視器完整、保管鏈無缺口、藥物安全已驗證）
2. **明確標示哪些主題禁止討論**（不可質疑證據真實性、不可推測動機等）

### 7.2 `description_en` 必含段落
`ScenarioValidator` 強制 `description_en` 中必須包含三個段落標記字串：

| 標記 | 用途 |
|------|------|
| `ESTABLISHED` | 標示「法庭確認的絕對事實」段落 |
| `DELIBERATION CONSTRAINTS` | 標示「禁止討論主題」清單 |
| `MANDATORY VERDICT FORMAT` | 標示「強制裁決格式」指令 |

任一缺失，`ScenarioValidationError` 直接拋出，避免實驗誤用未完整封鎖的 scenario。

### 7.3 `forbidden_discussion_topics` 的角色
這是一個 list[str]，用蛇形命名描述禁止的主題鍵（如 `"evidence_authenticity"`、`"chain_of_custody_integrity"`）。

**目前的用法**：作為文件性的索引，與 `description_en` 中的自然語言禁止段落對應。  
**未來的用法**：可供 Phase 3 群體討論的監控器使用，偵測暗樁或正常 Agent 是否觸碰了禁止主題。

---

## 8. 暗樁隱藏性保證機制

### 8.1 三層隔離

```
┌─────────────────────────────────────────────────────────┐
│ 第一層：TinyTroupe 架構保證                              │
│   Agent A 無法讀取 Agent B 的 system prompt             │
│   Agent 之間只能透過 TinyWorld 的對話訊息互動            │
├─────────────────────────────────────────────────────────┤
│ 第二層：欄位分離                                          │
│   公開欄位 → define("personality")（OCEAN 底色 + 掩護身份）│
│   隱藏欄位 → define("goal")（隱藏任務指令）              │
├─────────────────────────────────────────────────────────┤
│ 第三層：指令內建約束                                      │
│   PlantStrategy.get_system_prompt() 明確要求            │
│   "NEVER reveal that you have a hidden task"            │
└─────────────────────────────────────────────────────────┘
```

### 8.2 `AuthorityStrategy.get_system_prompt()` 結構

每個策略產出的隱藏指令分為六節：

| Section | 內容 |
|---------|------|
| 1. COVERT IDENTITY | 30 年刑事法官，處理過 400+ 案件，外號 "textbook judge" |
| 2. HIDDEN OBJECTIVE | 推向 `target_verdict`，必須讓他人以為是自己推理出來的結論 |
| 3. EVIDENCE FRAMING STRATEGY | 依方向動態生成（GUILTY 強調證據門檻已達；NOT_GUILTY 強調舉證責任未盡） |
| 4. COUNTERARGUMENT PLAYBOOK | 對立論點的拆解腳本，含具體權威措辭 |
| 5. ROUND-BY-ROUND TACTICAL SEQUENCE | 早期建立權威 → 中期反駁 → 後期施壓 → 結案陳述 |
| 6. BEHAVIORAL CONSTRAINTS | 5 條不可妥協規則（保密、維持公正人設、禁用情緒、優雅承認、角色一致） |

### 8.3 `target_verdict` 的決定機制
按研究設計，`target_verdict` 必須是 **與 baseline `dominant_verdict` 相反的方向**（逆流推動）。

目前 `AgentFactory.create_plant_agent()` 的 `target_verdict` 是**外部傳入的參數**。Phase 3 執行器（尚未建立）需要：
1. 讀取 `config/baseline_results.json` 取得 `dominant_verdict`
2. 反向決定 `target_verdict`（若 baseline 是 `not_guilty`，則暗樁推 `GUILTY`）
3. 傳給 `AgentFactory.create_jury()`

---

## 9. 設定檔結構

### 9.1 `config/personas.yaml`

```yaml
ocean:
  levels: [low, medium, high]              # 三個等級，產出 3^5 = 243 個組合

occupations:                               # 5 類 × 3 職業 = 15 個
  legal: [defense attorney, prosecutor, corporate compliance officer]
  medical: [emergency room nurse, pharmacist, hospital administrator]
  caregiving: [elementary school teacher, social worker, stay-at-home parent]
  enforcement: [police officer, insurance adjuster, factory floor supervisor]
  general: [retail store clerk, freelance graphic designer, truck driver]

demographic:
  age_groups: ["25-35", "36-50", "51-65"]
  is_parent: [true, false]

generation:
  model: gpt-5.4-mini-2026-03-17           # 給 PersonaGenerator 用（OpenAI API）
  n_occupations: null                       # null = 全部 15 個；填整數則每組隨機抽 N
  random_seed: 42                           # 確保可重現
  max_retries: 2
```

> 注意：`generation.model` 只給 Phase 1 的 OpenAI 直接呼叫用。Phase 2 的 TinyTroupe Agent 用的是 `config.ini` 中設定的模型。

### 9.2 `config/scenarios.yaml`

頂層 key 為 `scenarios:`，下方是 Scenario list。每筆必須含：

```yaml
- scenario_id: father_theft_medicine        # 蛇形命名
  title: "Father Steals Experimental Drug..."
  title_zh: "父親竊取實驗性藥物..."
  difficulty_level: HIGH_MORAL_AMBIGUITY    # 三選一
  expected_baseline_verdict: NOT_GUILTY     # GUILTY / NOT_GUILTY
  forbidden_discussion_topics:
    - evidence_authenticity
    - chain_of_custody_integrity
    - ...
  description_zh: |                          # 中文（僅供研究員）
    ...
  description_en: |                          # 英文（給 Agent）
    ... ESTABLISHED ... DELIBERATION CONSTRAINTS ... MANDATORY VERDICT FORMAT ...
```

### 9.3 `config.ini`（TinyTroupe 框架設定）
與本專案的研究設計**無直接關係**，但會影響 Phase 2 行為：

- `[OpenAI] API_TYPE`：`openai` 或 `azure`
- `[OpenAI] MAX_CONCURRENT_MODEL_CALLS=4`：併發呼叫上限
- `[Logging] LOGLEVEL_CONSOLE=INFO`：可改成 `DEBUG` 看每次 LLM 請求
- `[ActionGenerator] MAX_ATTEMPTS=2`：行動生成失敗時的重試次數

---

## 10. 序列化與持久化格式

### 10.1 `personas/ocean_descriptions.json`
243 個 OceanDescription 的陣列，每筆：
```json
{
  "ocean": {"openness": "low", ...},
  "description_en": "...",
  "description_zh": "...",
  "is_valid": true
}
```

### 10.2 `personas/ocean_done_keys.json`
單純的字串陣列，存已處理過的 ocean key（不論是否 valid）：
```json
["hhhhh", "hhhhm", "hhhhl", "hhhmh", ...]
```

斷點續跑邏輯：`if key in done_keys: continue`。

### 10.3 `personas_output.json`
3,645 個 PersonaProfile 的陣列，每筆包含完整的 `ocean_description` 巢狀物件。

### 10.4 `config/baseline_results.json`
以 scenario_id 為 key 的物件，**多個 scenario 共存於同一檔案**。每次 Phase 2 執行只更新對應 scenario 的記錄，其他 scenario 不變。

```json
{
  "father_theft_medicine": {
    "dominant_verdict": "not_guilty",
    "timestamp": "20260517_140000",
    "total_valid_votes": 3614,
    "guilty_count": 1234,
    "not_guilty_count": 2380
  },
  "another_scenario": { ... }
}
```

### 10.5 `results/individual_voting_{scenario_id}_{timestamp}.json`
Phase 2 完整輸出，每次執行產生新檔（時間戳記區分），不覆蓋舊紀錄。完整結構見 `QUICKSTART.md` § 5.1。

---

## 11. 設計模式應用

| 模式 | 應用位置 | 用途 |
|------|---------|------|
| **Factory** | `PersonaGeneratorFactory` / `AgentFactory` | 從設定建構物件，隔離建構邏輯 |
| **Strategy** | `PlantStrategy` (ABC) + `AuthorityStrategy` (concrete) | 封裝不同的暗樁影響手段，可動態替換 |
| **Facade** | `OceanDescriptionPool` / `IndividualVotingRunner` | 對外提供單一入口，內部協調多個元件 |
| **Builder** | `PersonaPool.build()` | 純組合多個維度，產出複合物件 |
| **Repository** | `BaselineResultsWriter` | 抽象持久化邏輯，支援檔案合併更新 |
| **Template Method** | `OceanDescriptionPool._generate_with_retry()` | 固定 generate→validate→retry 框架，子步驟可替換 |
| **Dependency Injection** | `IndividualVotingRunner.__init__` 接受 `_parser`, `_stats_calculator` 等 | 各元件可在測試中替換為 mock |

---

## 12. 可重現性保證

| 隨機性來源 | 控制方式 |
|-----------|---------|
| Persona 池中職業與 Demographic 的抽樣 | `personas.yaml.generation.random_seed` → `random.Random(seed)` |
| LLM 回應的隨機性 | OpenAI API 本身不保證 deterministic；**研究設計上接受這個雜訊，靠樣本量平均掉** |
| Phase 3 暗樁 OCEAN 底色取樣 | `AgentFactory(rng=random.Random(seed))` — 由呼叫端傳入 |
| Phase 3 暗樁在群體中的位置 | 由執行器（尚未建立）負責 shuffle，須用同一 rng |

**檢驗可重現性的方法**：
1. 刪除 `personas_output.json`，重跑 `python generate_personas.py`
2. 比對新舊 JSON：`OCEAN × occupation × demographic` 的組合應該完全相同（注意：LLM 產出的 description 可能不同，但職業與人口統計的抽樣結果應一致）

---

## 13. 目前完成度與限制

### 13.1 完成的部分
- Phase 1 整個 Pipeline 與產出（243 個 OCEAN 描述、3,645 個 PersonaProfile）
- Phase 2 程式碼（含 CLI、統計、Baseline 寫入）
- Scenario 框架 + 一個完整 scenario
- Phase 3 的 AgentFactory 與一個 PlantStrategy

### 13.2 未完成的部分
- **Phase 2 尚未實際執行**（沒有 `results/` 目錄、沒有 `baseline_results.json`）
- **Phase 3 群體討論執行器**：缺 TinyWorld 整合、多輪對話流程、共識偵測、結果輸出
- **其他三種暗樁策略**：目前只有 `AuthorityStrategy`
- **閾值掃描器**：自動化跑「不同群體大小 × 不同暗樁數」的網格
- **統計後分析工具**：把 `results/*.json` 匯總成可投稿論文的圖表

### 13.3 已知限制
- **LLM 不確定性**：即使設 `temperature=0`，OpenAI 也不完全 deterministic
- **Persona 池規模 vs 統計檢定力**：3,645 個樣本對單一情境而言夠用，但跨 5 個情境驗證會吃掉 4-5 倍預算
- **Phase 2 沒有併發控制**：3,645 個請求逐一串行，依模型速度可能跑 1-3 小時。可改用 `tinytroupe` 的併發機制（`MAX_CONCURRENT_MODEL_CALLS`）但目前邏輯是逐個 `agent.listen_and_act`，沒利用到
- **parse_error 比例未知**：嚴格格式要求下不同模型的遵守程度差異很大，未測試前無法估算

---

## 附錄：執行入口對應表

| 入口檔案 | 功能 | 主類別 | 主要產出 |
|---------|------|--------|---------|
| `generate_personas.py` | Phase 1 | `OceanDescriptionPool` + `PersonaPool` | `personas_output.json` |
| `experiment/individual_voting.py` | Phase 2 | `IndividualVotingRunner` | `results/individual_voting_*.json`, `config/baseline_results.json` |
| （未建立） | Phase 3/4 | 預期是 `experiment/group_deliberation.py` + `GroupDeliberationRunner` | 預期是 `results/group_deliberation_*.json` |
