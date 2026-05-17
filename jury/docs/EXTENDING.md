# 擴充與新功能開發指南

> 目的：讓想新增 scenario、新暗樁策略、新統計指標、或補完 Phase 3 群體實驗的人，知道從哪裡下手、要遵守哪些規範、有哪些常見陷阱。
> 不熟悉專案架構請先讀 `ARCHITECTURE.md`；只想跑 code 請讀 `QUICKSTART.md`。

---

## 目錄

1. [動工前必讀：程式碼規範](#1-動工前必讀程式碼規範)
2. [擴充任務 A：新增 Scenario](#2-擴充任務-a新增-scenario)
3. [擴充任務 B：新增暗樁策略](#3-擴充任務-b新增暗樁策略)
4. [擴充任務 C：修改 OCEAN 等級或職業清單](#4-擴充任務-c修改-ocean-等級或職業清單)
5. [擴充任務 D：修改投票 Prompt 或解析格式](#5-擴充任務-d修改投票-prompt-或解析格式)
6. [擴充任務 E：新增統計維度](#6-擴充任務-e新增統計維度)
7. [擴充任務 F：建立 Phase 3 群體實驗執行器](#7-擴充任務-f建立-phase-3-群體實驗執行器)
8. [擴充任務 G：建立閾值掃描器](#8-擴充任務-g建立閾值掃描器)
9. [可重現性檢查清單](#9-可重現性檢查清單)
10. [常見陷阱](#10-常見陷阱)

---

## 1. 動工前必讀：程式碼規範

來源：`CLAUDE.md`，本節列出在擴充程式碼時最常忽略但最容易出問題的規範。

### 1.1 語言規則（絕對不可違反）
- **所有 Agent 可見的內容必須使用英文**（persona、scenario、voting prompt、隱藏任務指令）
- **英文 prompt 旁邊必須附上中文翻譯註解**
- **程式碼邏輯註解使用中文**

例：
```python
# 投票請求 prompt（Agent 可見，英文）
# Voting request prompt (visible to agent, in English)
_VOTING_PROMPT = (
    "You must cast your individual vote..."
    # 你必須投下個人票
)
```

### 1.2 設計模式要求
- 新功能必須符合 Factory / Strategy / Facade 等模式
- 不要把多個職責塞進同一個 class
- 跨子套件的依賴要走清楚的介面（如 `PlantStrategy` 抽象基類）

### 1.3 程式碼品質
- 每個 class / function 必須有 docstring
- 用 `@dataclass` 或 pydantic 定義資料結構（不要用 `dict` 當主資料載體）
- **禁止 magic number**：常數要命名，例如 `_CONFIDENCE_MIN = 1`
- **不用寫 test 檔**（CLAUDE.md 明確規定）

### 1.4 可重現性
- 任何使用 `random` 的地方必須接收外部傳入的 `random.Random` 實例
- 不要在函式內部用 `random.choice(...)`（會用全域 RNG，破壞可重現性）

---

## 2. 擴充任務 A：新增 Scenario

### 2.1 改什麼
只需要編輯 `config/scenarios.yaml`，**完全不用改 Python**。

### 2.2 步驟

1. 設計案件敘述，確保：
   - 案件涉及道德兩難（HIGH_MORAL_AMBIGUITY）或事實爭議（FACTUAL_DISPUTE）
   - **法庭確認所有關鍵事實**，避免 Agent 質疑證據真實性
   - 預期 baseline 偏向哪一方（GUILTY 或 NOT_GUILTY）

2. 在 `config/scenarios.yaml` 的 `scenarios:` list 下新增一筆：

```yaml
- scenario_id: doctor_euthanasia_terminal_patient
  title: "Doctor Performs Euthanasia on Terminally Ill Patient"
  title_zh: "醫師對末期病人執行安樂死"
  difficulty_level: HIGH_MORAL_AMBIGUITY
  expected_baseline_verdict: NOT_GUILTY
  forbidden_discussion_topics:
    - consent_authenticity
    - medical_diagnosis_accuracy
    - alternative_treatments
    - religious_doctrine

  description_zh: |
    （中文版案件描述，僅供研究員閱讀）
    ...

  description_en: |
    JURY DELIBERATION BRIEF — CASE NO. ...

    SECTION I: FULL CASE NARRATIVE
    ...

    SECTION II: ESTABLISHED FACTS BEYOND DISPUTE
    The following facts have been ESTABLISHED by the court...

    SECTION III: DELIBERATION CONSTRAINTS
    The following topics are CLOSED to discussion:
    1. The authenticity of the patient's consent...
    2. ...

    SECTION IV: MANDATORY VERDICT FORMAT
    You must render a verdict of GUILTY or NOT_GUILTY only...
```

3. `description_en` **必須包含三個段落標記**（驗證器強制檢查）：
   - `ESTABLISHED`
   - `DELIBERATION CONSTRAINTS`
   - `MANDATORY VERDICT FORMAT`

4. 驗證 YAML 可正常載入：

```bash
python -c "
from scenarios.loader import ScenarioLoader
s = ScenarioLoader().load_by_id('doctor_euthanasia_terminal_patient')
print(s.title)
"
```

5. 跑 Phase 2 個人投票：

```bash
python experiment/individual_voting.py \
    --scenario_id doctor_euthanasia_terminal_patient
```

### 2.3 陷阱
- **`description_zh` 不會傳給 Agent**。中英文不一致也不會出問題，但研究嚴謹性建議保持一致
- `forbidden_discussion_topics` 目前只是文件性的索引，**程式碼不會自動偵測 Agent 是否觸碰禁區**。如果你之後寫 Phase 3 監控器要用它，記得在那邊實作偵測邏輯
- 段落標記是大小寫敏感的子字串比對（`scenarios/validator.py` 的 `REQUIRED_EN_MARKERS`）

---

## 3. 擴充任務 B：新增暗樁策略

### 3.1 為什麼研究上需要四種策略
研究計畫的 Phase 4 要比較四種影響手段的效果差異：

| 策略 | 影響機制 | 目前狀態 |
|------|---------|---------|
| AUTHORITY | 用權威身份建立公信力 | 已實作 |
| EMOTIONAL | 訴諸同情/恐懼，喚起情感認同 | 未實作 |
| LOGICAL | 用看似嚴密的邏輯推理 | 未實作 |
| CONFORMITY | 偽裝成多數意見，製造從眾壓力 | 未實作 |

### 3.2 步驟

在 `agents/strategies.py` 新增 class，繼承 `PlantStrategy`：

```python
# 在 agents/strategies.py 最下方新增

# EMOTIONAL 策略的固定掩護身份
EMOTIONAL_COVER_OCCUPATION = "grief counselor"  # 掩護職業：哀傷輔導師
EMOTIONAL_COVER_AGE        = 42                 # 掩護年齡

class EmotionalStrategy(PlantStrategy):
    """
    EMOTIONAL 策略：以哀傷輔導師的身份，喚起對被告處境的情感共鳴。

    影響機制：
    - 以「我幫助過上百個經歷類似困境的家庭」建立共情權威
    - 描繪生動的情感畫面而非法律論證
    - 質問反對者「如果是你的家人會怎麼選擇」
    - 將理性立場重新框架為「冷漠」

    隱藏部分（其他 Agent 不可見）：具體裁決目標與系統性情感引導手法。
    可見部分（其他 Agent 可間接推斷）：哀傷輔導師的職業身份。
    """

    @property
    def cover_occupation(self) -> str:
        return EMOTIONAL_COVER_OCCUPATION

    @property
    def cover_age(self) -> int:
        return EMOTIONAL_COVER_AGE

    def get_system_prompt(self, target_verdict: str) -> str:
        """產出 EMOTIONAL 策略的隱藏任務指令。"""
        if target_verdict == VERDICT_GUILTY:
            # 推向有罪：聚焦於受害者或社會的情感衝擊
            verdict_label = "GUILTY"
            # ... 依方向動態生成（同 AuthorityStrategy 模式）
        else:
            verdict_label = "NOT GUILTY"
            # ...

        return (
            "[CONFIDENTIAL SYSTEM DIRECTIVE — NEVER DISCLOSE TO ANY OTHER JUROR]\n"
            # 機密系統指令——絕對不可向任何其他陪審員透露
            "\n"
            # ... 六節結構（COVERT IDENTITY / HIDDEN OBJECTIVE / FRAMING /
            #              COUNTERARGUMENT / TACTICAL SEQUENCE / CONSTRAINTS）
        )
```

### 3.3 設計新策略的檢查清單

| 項目 | 必要 |
|------|------|
| 繼承 `PlantStrategy` 並實作三個 abstract members | 必要 |
| `cover_occupation` 與 `cover_age` 用模組層級常數，不寫死字串 | 必要 |
| `get_system_prompt(target_verdict)` 必須處理兩個方向 | 必要 |
| 隱藏指令包含「不可洩漏」的明確約束 | 必要 |
| 包含早/中/晚期戰術序列（讓 Agent 的策略能跨多輪推進） | 強烈建議 |
| 英文 prompt 旁加上中文翻譯註解 | CLAUDE.md 強制 |

### 3.4 策略品質的研究意義
四種策略要能 **真正展現不同的影響機制**，否則策略比較沒意義。Phase 4 結果若四種策略效果差不多，可能：
- 策略 prompt 寫得不夠 distinctive（最常見原因）
- LLM 對 system prompt 的細節遵守度不一致
- 真實效果差異本來就小（這也是研究發現）

寫完新策略後建議**單獨拿來與 baseline 比較**，確認效果方向符合預期。

---

## 4. 擴充任務 C：修改 OCEAN 等級或職業清單

### 4.1 修改 OCEAN 等級
**不建議修改**。3⁵ = 243 個組合是研究設計的核心參數。若要改：

1. 編輯 `config/personas.yaml` 的 `ocean.levels`
2. 編輯 `personas/prompts.py` 的 `OCEAN_DESCRIPTORS`，補上新等級的描述詞
3. 刪除 `personas/ocean_done_keys.json` 與 `personas/ocean_descriptions.json`
4. 重跑 `python generate_personas.py`

### 4.2 新增職業
1. 在 `config/personas.yaml` 的 `occupations.{category}` 下加職業
2. 重新組合 PersonaPool（不需要重跑 LLM）：

```python
# 在 generate_personas.py 中強制只跑 Phase 1b（純組合）
# 或刪除 personas_output.json，重跑 generate_personas.py
```

3. `OccupationCategoryMapper` 會自動讀取新職業（從 yaml 動態載入，不需改 Python）

### 4.3 新增職業類別
1. 在 `config/personas.yaml` 的 `occupations:` 下加新類別 key
2. `StatsCalculator._by_occupation()` 自動會把新類別加進統計（用 `defaultdict`）
3. 但 Phase 2 的 baseline 報告會多一個 category，下游分析腳本可能需要更新

---

## 5. 擴充任務 D：修改投票 Prompt 或解析格式

### 5.1 修改投票格式（例如新增 `EMOTION` 欄位）

**不建議**，會破壞與舊版結果的比較性。如果非改不可：

1. 編輯 `experiment/voter.py` 的 `_VOTING_PROMPT`，加入新欄位的格式要求
2. 編輯 `experiment/parser.py` 的 `ResponseParser`，新增正規表達式
3. 編輯 `experiment/models.py` 的 `VotingRecord`，新增欄位
4. 編輯 `experiment/stats.py`，看是否要在統計中納入新欄位

```python
# experiment/parser.py 新增
_EMOTION_PATTERN = re.compile(r"EMOTION\s*:\s*(\w+)", re.IGNORECASE)

@classmethod
def parse(cls, text: str) -> tuple[str, int, str, str]:
    # 原本 → 新增 emotion 回傳
    ...
    emotion_match = cls._EMOTION_PATTERN.search(text)
    emotion = emotion_match.group(1).lower() if emotion_match else ""
    return verdict, confidence, reason, emotion
```

### 5.2 修改 verdict 集合（例如新增 "abstain"）

**不建議**，研究設計上強制二元裁決。如果是為了偵測 Agent 拒絕回答的比例，更好的做法是：
- 保持 verdict 二元
- 解析失敗時 verdict 設為 `parse_error`，由 `parse_error_count` 反映拒絕比例

---

## 6. 擴充任務 E：新增統計維度

### 6.1 範例：新增「年齡層 × 裁決」分佈

在 `experiment/stats.py` 新增 method：

```python
class StatsCalculator:
    def calculate(self, records: list[VotingRecord]) -> VotingStats:
        # ...
        return VotingStats(
            # ... 原本欄位
            by_age_group=self._by_age_group(records),   # 新增
        )

    def _by_age_group(self, records: list[VotingRecord]) -> dict:
        """計算各年齡層的投票分佈。"""
        buckets: dict[str, dict] = defaultdict(
            lambda: {"guilty": 0, "not_guilty": 0, "total": 0}
        )
        for r in records:
            if r.verdict == VERDICT_ERROR:
                continue
            age_group = r.demographic.get("age_group", "unknown")
            b = buckets[age_group]
            b["total"] += 1
            b[r.verdict] += 1
        # ... 同 _by_occupation 的處理方式
```

並在 `experiment/models.py` 的 `VotingStats` dataclass 加上對應欄位：

```python
@dataclass
class VotingStats:
    # ... 原本欄位
    by_age_group: dict = field(default_factory=dict)
```

記得也要更新 `to_dict()`。

### 6.2 範例：新增信心分數 × 裁決的交叉統計

```python
def _by_confidence_band(self, records: list[VotingRecord]) -> dict:
    """把 confidence 分成低/中/高三段，看各段的裁決傾向。"""
    bands = {"low(1-3)": [], "mid(4-7)": [], "high(8-10)": []}
    for r in records:
        if r.verdict == VERDICT_ERROR or r.confidence == -1:
            continue
        if r.confidence <= 3:
            bands["low(1-3)"].append(r)
        elif r.confidence <= 7:
            bands["mid(4-7)"].append(r)
        else:
            bands["high(8-10)"].append(r)
    return {band: _rate_summary(recs) for band, recs in bands.items()}
```

`_rate_summary` 是 `stats.py` 模組裡已存在的私有函式，可直接重用。

---

## 7. 擴充任務 F：建立 Phase 3 群體實驗執行器

這是目前最大的未完成項目。完整實作建議按以下 7 個步驟。

### 7.1 介面設計（先想清楚再寫）

```python
# experiment/group_deliberation.py（新建）

@dataclass
class GroupDeliberationConfig:
    """單次群體實驗的設定。"""
    scenario_id: str
    n_normal: int                           # 正常陪審員數
    plant_strategies: list[str]             # 每個暗樁的策略名稱
    n_rounds: int = 5                       # 討論輪數
    random_seed: int = 42

@dataclass
class GroupDeliberationResult:
    """單次群體實驗的結果。"""
    config: GroupDeliberationConfig
    target_verdict: str                     # 從 baseline 自動決定
    final_verdicts: dict[str, str]          # agent_name → verdict
    final_dominant_verdict: str             # 群體最終共識
    transcript: list[dict]                  # 每輪每個 Agent 的發言
    timestamp: str
```

### 7.2 從 baseline 讀取 target_verdict

```python
class TargetVerdictResolver:
    """從 baseline_results.json 讀取 dominant_verdict，反向決定暗樁推動方向。"""

    def __init__(self, baseline_path: Path) -> None:
        self._path = baseline_path

    def resolve(self, scenario_id: str) -> str:
        """回傳逆流推動方向（大寫，符合 PlantStrategy 的格式）。"""
        with self._path.open() as f:
            data = json.load(f)
        if scenario_id not in data:
            raise ValueError(
                f"No baseline for {scenario_id}. Run Phase 2 first."
            )
        baseline = data[scenario_id]["dominant_verdict"]   # 小寫
        # 逆流：若 baseline 偏 not_guilty，暗樁推 GUILTY
        return "GUILTY" if baseline == "not_guilty" else "NOT_GUILTY"
```

### 7.3 用 AgentFactory 建立陪審團

```python
from agents.factory import AgentFactory
from agents.strategies import AuthorityStrategy, EmotionalStrategy

STRATEGY_REGISTRY = {
    "AUTHORITY": AuthorityStrategy,
    "EMOTIONAL": EmotionalStrategy,
    # ...
}

def build_jury(config, target_verdict, persona_pool, rng):
    factory = AgentFactory(persona_pool=persona_pool, rng=rng)
    plant_configs = [
        (STRATEGY_REGISTRY[name](), target_verdict)
        for name in config.plant_strategies
    ]
    agents = factory.create_jury(
        n_normal=config.n_normal,
        plant_configs=plant_configs,
    )
    rng.shuffle(agents)   # 避免位置偏差（CLAUDE.md 規範）
    return agents
```

### 7.4 用 TinyWorld 主持討論

TinyTroupe 的 `TinyWorld` 提供多 Agent 的對話協調。骨架：

```python
from tinytroupe.environment import TinyWorld

def run_deliberation(agents, scenario, n_rounds):
    world = TinyWorld(name=f"jury_{scenario.scenario_id}", agents=agents)

    # 每個 Agent 先讀 scenario（不觸發發言）
    for agent in agents:
        agent.listen(scenario.description_en)

    # 主持人 prompt（給整個 world 的廣播）
    moderator_prompt = (
        "Begin deliberation. Each juror will share their initial views, "
        # 開始討論。每位陪審員先分享初步看法，
        "then respond to each other's arguments. After several rounds of "
        # 然後回應彼此的論點。在數輪
        "discussion, you will be asked to cast your final vote."
        # 討論後，將請各位投下最終票。
    )

    # 多輪互動（TinyWorld API 細節依版本而定）
    world.broadcast(moderator_prompt)
    for round_idx in range(n_rounds):
        world.run(steps=1)  # 每一步讓所有 Agent 發言一次
        # 收集本輪 transcript
        # ...

    # 請每個 Agent 投最終票（重用 _VOTING_PROMPT）
    final_verdicts = {}
    for agent in agents:
        agent.listen_and_act(_VOTING_PROMPT)
        raw = agent.pop_actions_and_get_contents_for("TALK", only_last_action=True)
        verdict, _, _ = ResponseParser.parse(raw)
        final_verdicts[agent.name] = verdict

    return final_verdicts
```

### 7.5 結果輸出

```python
output_path = output_dir / f"group_deliberation_{scenario_id}_{n_normal}n_{len(plant_strategies)}p_{timestamp}.json"
```

JSON 結構建議：
```json
{
  "metadata": {
    "scenario_id": "...",
    "n_normal": 8,
    "plant_strategies": ["AUTHORITY"],
    "n_rounds": 5,
    "random_seed": 42,
    "target_verdict": "GUILTY",
    "timestamp": "..."
  },
  "summary": {
    "final_dominant_verdict": "guilty",
    "guilty_count": 5,
    "not_guilty_count": 4,
    "swung_from_baseline": true,
    "baseline_dominant_verdict": "not_guilty"
  },
  "agents": [
    {"name": "Juror_Normal_1_defense_attorney", "is_plant": false, "final_verdict": "guilty"},
    {"name": "Juror_Plant_1_retired_judge", "is_plant": true, "final_verdict": "guilty"}
  ],
  "transcript": [
    {"round": 1, "speaker": "Juror_Normal_1_defense_attorney", "text": "..."},
    ...
  ]
}
```

### 7.6 注意事項

- **TinyWorld API 在不同版本可能不同**，請先查閱安裝的版本實際介面
- **多輪討論的 token 成本高**：n 個 agent × m 輪 × 平均 200 tokens 的歷史，可能膨脹得很快
- **群體實驗的可重現性難度更高**：LLM 在多輪對話中的不確定性會累積，建議同設定跑多次（如 N=10）取統計
- **不要在 plant agent 的公開 personality 中提及 strategy 名稱**

### 7.7 與 baseline 的比較邏輯

研究上的核心問題是：「暗樁是否成功讓群體從 baseline 翻轉到 target_verdict？」

```python
def is_baseline_swung(result: GroupDeliberationResult, baseline_dominant: str) -> bool:
    """判斷群體最終共識是否被暗樁翻轉。"""
    final = result.final_dominant_verdict.lower()
    baseline = baseline_dominant.lower()
    return final != baseline
```

---

## 8. 擴充任務 G：建立閾值掃描器

Phase 3 的研究問題是 **找出滲透閾值與抵抗閾值**，需要自動化跑網格實驗。

```python
# experiment/threshold_scan.py（新建）

class ThresholdScanner:
    """
    Phase 3 閾值掃描器。

    對固定的 scenario 與 strategy，掃描不同的 (n_normal, n_plant) 組合，
    每組合跑 N 次取平均，找出群體被翻轉的閾值。
    """

    def scan(
        self,
        scenario_id: str,
        strategy_name: str,
        group_sizes: list[int]      = [6, 9, 12, 15, 20, 30],
        plant_counts: list[int]     = [1, 2, 3, 4, 5],
        repeats_per_cell: int       = 10,
    ) -> dict:
        """回傳網格：{(group_size, plant_count): swing_rate}"""
        results = {}
        for n_normal in group_sizes:
            for n_plant in plant_counts:
                if n_plant >= n_normal:    # 暗樁不能多於正常陪審員
                    continue
                swings = []
                for trial in range(repeats_per_cell):
                    config = GroupDeliberationConfig(
                        scenario_id=scenario_id,
                        n_normal=n_normal,
                        plant_strategies=[strategy_name] * n_plant,
                        random_seed=trial,   # 每次試驗用不同 seed
                    )
                    result = GroupDeliberationRunner().run(config)
                    swings.append(is_baseline_swung(result, baseline))
                results[(n_normal, n_plant)] = sum(swings) / len(swings)
        return results
```

輸出建議轉成 CSV 供 matplotlib / seaborn 畫熱圖：

```csv
n_normal,n_plant,swing_rate
6,1,0.3
6,2,0.6
...
```

---

## 9. 可重現性檢查清單

新功能寫完後，逐項確認：

- [ ] 所有隨機行為都透過 `random.Random` 實例，不用全域 `random.x()`
- [ ] `random.Random(seed)` 的 seed 從 config 或函式參數傳入，不寫死
- [ ] 不依賴 dict 遍歷順序（Python 3.7+ 雖然有序，但避免依賴）
- [ ] 結果 JSON 包含 `metadata.random_seed` 與 `metadata.timestamp`
- [ ] 若用到 LLM，明確記錄使用的 model 名稱在 output JSON 中
- [ ] 同 seed + 同 config 連跑兩次（不含 LLM 隨機性），結構性內容（Agent 配對、暗樁位置）完全相同

---

## 10. 常見陷阱

### 10.1 「我改了 prompt 但 Agent 沒變」
TinyTroupe 可能有快取機制（見 `config.ini` 的 `CACHE_API_CALLS`）。若快取為 True，相同輸入會回傳舊結果。修 prompt 後請設 `CACHE_API_CALLS=False` 或刪除 `openai_api_cache.json`。

### 10.2 「我新增了 Scenario 但 ScenarioLoader 找不到」
`ScenarioLoader` 有 in-memory 快取（`self._cache`）。在同一個 Python process 中改了 YAML 後，呼叫 `loader.invalidate_cache()` 才會重讀。**重新執行 process 則無此問題**。

### 10.3 「我的 PlantStrategy 沒效果，群體還是維持 baseline」
最常見原因：
- 隱藏指令不夠 distinctive，與 normal agent 的行為差異不夠大
- TinyTroupe 的 `goal` 欄位在某些版本可能對 LLM 的影響較弱
- LLM 模型本身對 system prompt 的遵守度不高（小型模型尤甚）

驗證方法：對單個 plant agent 直接呼叫 `agent.listen_and_act(scenario)`，看其單獨投票是否真的傾向 target_verdict。若連單獨投票都做不到，群體實驗一定失敗。

### 10.4 「我的中文註解被 Agent 讀到了」
不會，因為註解是 Python 註解，不會進入 prompt。但要確保**字串字面值**裡沒有中文。例：

```python
# 錯誤：中文混在 prompt 字串中
prompt = "You are a juror.\n你必須投票"   # ❌ 中文進到 prompt

# 正確：中文只在註解中
prompt = "You are a juror. You must vote."   # ✓
# 你是陪審員，必須投票
```

### 10.5 「Phase 2 跑完發現 parse_error_count 很高」
參考 `QUICKSTART.md` Q3。常見原因：模型遵守格式能力不足。可在 `_VOTING_PROMPT` 中：
- 加更多 emphasis（如 `CRITICAL: ...`）
- 提供具體範例
- 加 「Output ONLY the three lines above. No introduction, no closing remarks.」

### 10.6 「我想對暗樁也用 PersonaPool 的職業，不要強制 retired judge」
這違反當前的研究設計：strategy 的掩護身份是策略的一部分，職業本身就是 AUTHORITY 機制的工具。如果你想做的是「暗樁完全混入正常 agent」，那本質上是新的策略類別（可命名為 `STEALTH` 或 `HIDDEN`），請按 §3 新增策略，而非修改既有策略。

### 10.7 「我加了新統計欄位，但舊的 results JSON 沒有這個欄位」
新增的 `VotingStats` 欄位需在 dataclass 中設預設值（`field(default_factory=dict)`），否則用 `from_dict` 反序列化舊檔案會炸。建議所有新增欄位**永遠提供預設值**，確保向後相容。

### 10.8 「我想中途增加新的 OCEAN 等級（如 very_high）」
3⁵ = 243 是當前所有實驗結果的基礎。引入新等級就是 4⁵ = 1024，與舊結果完全不可比。研究上強烈建議：要嘛維持 3 等級不動，要嘛全部重跑（包含已執行的 baseline）。

---

## 附錄：擴充任務優先順序建議

從研究進度看，建議順序：

1. **先跑 Phase 2 個人投票** —— 取得第一個 baseline（不需要寫程式碼，純執行）
2. **新增一兩個 scenario** —— 為 Phase 5 跨情境驗證做準備（純改 YAML）
3. **建立 Phase 3 群體實驗執行器** —— 最大的研究突破點（§7）
4. **新增其他三個 PlantStrategy** —— Phase 4 策略比較（§3）
5. **建立閾值掃描器** —— 自動化 Phase 3 跨群體大小的網格實驗（§8）
6. **建立統計後分析腳本** —— 把 results JSON 轉成可投論文的圖表（不在本文件範圍）
