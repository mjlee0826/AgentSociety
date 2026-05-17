# 快速上手指南

> 目的：讓只想把 code 跑起來、看到結果的人，能在 10 分鐘內完成。
> 完整架構說明請看 `ARCHITECTURE.md`；要擴充新功能請看 `EXTENDING.md`。

---

## 1. 系統需求

| 項目 | 需求 |
|------|------|
| 作業系統 | Linux / macOS / Windows（本專案在 Linux 6.17 上開發） |
| Python | 3.10 以上（程式使用 `from __future__ import annotations` 與 `tuple[...]` 等型別語法） |
| OpenAI API Key | Phase 1 生成 Persona 池需要；Phase 2 個人投票每張票會呼叫一次 LLM |
| 磁碟空間 | < 100 MB（含 Persona 池與結果 JSON） |

---

## 2. 安裝步驟

### 2.1 安裝 Python 套件

```bash
pip install openai pyyaml tqdm
```

### 2.2 安裝 TinyTroupe

本專案依賴 Microsoft TinyTroupe 框架建立 Agent。請依官方說明安裝：

```bash
# 從 GitHub 安裝（請依當時官方建議方式為準）
pip install git+https://github.com/microsoft/TinyTroupe.git
```

驗證安裝：

```bash
python -c "from tinytroupe.agent import TinyPerson; print('OK')"
```

### 2.3 設定 API Key

把 OpenAI API Key 設成環境變數：

```bash
export OPENAI_API_KEY="sk-..."
```

> Phase 1 的 `personas/factory.py` 與 TinyTroupe 都會自動從這個環境變數讀取。

### 2.4 確認 TinyTroupe 設定檔

專案根目錄下有 `config.ini`，這是 TinyTroupe 自己的設定檔（不要與 `config/personas.yaml` 混淆）。預設值已可使用，**通常不需要修改**。

如要使用 Azure OpenAI，把 `API_TYPE=openai` 改成 `API_TYPE=azure`，並設定 `AZURE_API_VERSION`。

---

## 3. 目錄結構速覽

```
jury/
├── config/
│   ├── personas.yaml           ← Persona 生成設定（OCEAN 等級、職業清單、model 名稱）
│   ├── scenarios.yaml          ← 實驗情境（目前一個：父親竊藥救女）
│   └── baseline_results.json   ← Phase 2 跑完後自動產生
├── personas/
│   ├── ocean_descriptions.json ← 已產出的 243 個 OCEAN 純人格描述（已存在）
│   └── ocean_done_keys.json    ← 斷點續跑用的進度檔（已存在）
├── personas_output.json        ← 3,645 個完整 PersonaProfile（已存在）
├── results/                    ← Phase 2 結果輸出（首次執行才會建立）
├── generate_personas.py        ← Phase 1 入口
└── experiment/
    └── individual_voting.py    ← Phase 2 入口
```

---

## 4. 執行流程

### 4.1 Phase 1 — Persona 池生成

**狀態：已完成**。`personas_output.json` 與 `personas/ocean_descriptions.json` 已存在於 repo 中，**不需要重跑**。

如果要重跑（例如想換模型重新生成）：

```bash
cd /home/mjlee/桌面/AgentSociety/jury
python generate_personas.py
```

> **重跑前注意**：刪除 `personas/ocean_done_keys.json` 才會重新生成全部 243 個；
> 否則只會補生成不在 done_keys 裡的組合。
> 重跑會呼叫 OpenAI API 約 243~729 次（含重試），有實際費用。

選用參數：

```bash
python generate_personas.py \
    --config config/personas.yaml \
    --output personas_output.json
```

成功標誌：終端機顯示 `Valid OCEAN descriptions: 243 / 243`。

---

### 4.2 Phase 2 — 個人投票實驗

**狀態：程式碼完成，從未跑過**。這是目前可以馬上執行的下一步。

```bash
cd /home/mjlee/桌面/AgentSociety/jury
python experiment/individual_voting.py
```

預設行為：
- 讀取 `personas_output.json` 中所有 `is_valid=True` 的 PersonaProfile（3,645 個）
- 對 `father_theft_medicine` 這個 scenario 逐一投票
- 進度條由 tqdm 顯示
- 把結果寫到 `results/individual_voting_father_theft_medicine_{timestamp}.json`
- 把 `dominant_verdict` 寫到 `config/baseline_results.json`

選用參數：

```bash
python experiment/individual_voting.py \
    --scenario_id father_theft_medicine \
    --persona_pool personas_output.json \
    --output_dir results
```

**成本警告**：3,645 個 Persona 各呼叫一次 LLM，依使用的模型不同，總成本可能在數美金到數十美金之間。要先小規模驗證，請先改 `personas/pool.py` 的 `n_occupations` 設為小數字（例如 3），重生 Persona 池後再跑。

---

## 5. 結果在哪裡

跑完 Phase 2 後：

### 5.1 完整實驗紀錄
路徑：`results/individual_voting_{scenario_id}_{timestamp}.json`

結構：
```json
{
  "metadata": {
    "scenario_id": "father_theft_medicine",
    "scenario_title": "Father Steals Experimental Drug...",
    "timestamp": "20260517_140000",
    "total_personas": 3645,
    "persona_pool_path": "..."
  },
  "summary": {
    "total": 3645,
    "guilty_count": 1234,
    "not_guilty_count": 2380,
    "parse_error_count": 31,
    "guilty_rate": 0.3415,
    "not_guilty_rate": 0.6585,
    "dominant_verdict": "not_guilty",
    "by_occupation_category": { ... },
    "by_ocean_dimension": { ... }
  },
  "records": [
    {
      "persona_id": "lmhlh_defense_attorney_36-50_1",
      "ocean_profile": { ... },
      "verdict": "not_guilty",
      "confidence": 8,
      "reason": "...",
      "raw_response": "..."
    },
    ...
  ]
}
```

### 5.2 Baseline 摘要
路徑：`config/baseline_results.json`

僅儲存後續暗樁實驗會用到的 `dominant_verdict`，多個 scenario 共存於同一檔案：

```json
{
  "father_theft_medicine": {
    "dominant_verdict": "not_guilty",
    "timestamp": "20260517_140000",
    "total_valid_votes": 3614,
    "guilty_count": 1234,
    "not_guilty_count": 2380
  }
}
```

---

## 6. 常見問題排除

### Q1：`ModuleNotFoundError: No module named 'tinytroupe'`
→ TinyTroupe 沒裝好。回到 2.2 重裝。

### Q2：`openai.AuthenticationError: ...`
→ API Key 未設定或無效。確認 `echo $OPENAI_API_KEY` 有輸出。

### Q3：Phase 2 跑到一半 LLM 回應無法解析（parse_error）很多
→ 表示模型沒有遵守強制格式。可：
1. 換成能力較強的模型（修改 `config/personas.yaml` 的 `generation.model`）
2. 但 Phase 2 用的不是這個 model — 它用的是 TinyTroupe 預設模型，由 `config.ini` 控制
3. 解析失敗的記錄 `verdict="parse_error"` 不會被算進 baseline 統計

### Q4：想要中斷 Phase 1 後繼續
→ 直接 Ctrl+C 停止。下次執行 `generate_personas.py` 會自動跳過 `ocean_done_keys.json` 中已完成的組合。

### Q5：Phase 2 不能中斷續跑嗎？
→ 目前不支援。3,645 個 Persona 一次跑完，途中失敗要重跑。要長時間執行請用 `nohup` 或 `screen`：

```bash
nohup python experiment/individual_voting.py > phase2.log 2>&1 &
```

### Q6：想要先試小規模看看 Pipeline 通不通
→ 編輯 `experiment/individual_voting.py`，在 `IndividualVotingRunner.run()` 的迴圈前加：
```python
personas = personas[:10]   # 暫時只跑 10 個
```
跑完確認 `results/` 有檔案後再恢復。

### Q7：「Scenario validation failed: description_en is missing required section marker」
→ 你修改了 `config/scenarios.yaml` 的 `description_en`，但拿掉了 `DELIBERATION CONSTRAINTS` / `MANDATORY VERDICT FORMAT` / `ESTABLISHED` 其中一個段落標記。把它加回去。

---

## 7. 下一步

- 想了解每個檔案的職責與資料流動 → `ARCHITECTURE.md`
- 想新增新的實驗情境、新的暗樁策略、或新的統計指標 → `EXTENDING.md`
- 想跑 Phase 3 群體討論實驗 → **尚未實作**，請看 `EXTENDING.md` 的「建立 Phase 3 群體實驗執行器」章節
