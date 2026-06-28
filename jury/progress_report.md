# AI Agent 群體決策影響力研究：進度報告
**Influence Infiltration in AI Agent Collective Decision-Making: Progress Report**

---

> 以下為**中文版**報告，英文版請見下方分隔線後。
> The **English version** follows after the divider below.

---

# ═══════════════════════════════════════
# 中文版
# ═══════════════════════════════════════

## AI Agent 群體決策中的影響力滲透實驗：進度報告

**國立臺灣大學資訊工程學系碩士研究**
**日期：2026 年 5 月**

---

## 一、研究背景

本研究探討在 AI Agent 模擬的群體決策中，安插「暗樁（planted agents / confederate agents）」是否能系統性地改變群體的最終決策方向，以及多少正常 Agent 足以抵禦暗樁的影響。這一研究問題的靈感來自社會心理學中的經典文獻——從 Asch（1951, 1956）的從眾實驗到 Latané & Darley（1968）的旁觀者效應研究——這些實驗揭示了人類在群體情境下的決策偏誤，但因倫理與執行困難，難以在真實人類身上大規模重複。本研究試圖以 LLM Agent 作為人類的代理，在受控環境中系統性地探索這些現象的閾值條件。

---

## 二、實驗挑戰與方法調整

### 2.1 Temperature 調整的嘗試與困境

在早期實驗設計中，我們試圖透過調整模型的 **temperature 參數**來增加 Agent 決策的多樣性與不確定性，以避免所有 Agent 趨同於單一答案，使暗樁的影響更容易被觀測。然而此路線遭遇兩個連續障礙：

1. **GPT-5 不支援 temperature 設定**：我們最初使用的 GPT-5 模型並不開放使用者自訂 temperature 參數，無法按計畫調整輸出隨機性。

2. **切換至 GPT-4 後出現人格一致性問題**：改用 GPT-4 後，雖然 temperature 調整可行，但我們觀察到 Agent 的實際發言風格與其預設人格（persona）之間出現顯著不一致——Agent 的行為模式不夠穩定地反映其人格設定，削弱了實驗中「不同人格導致不同決策傾向」的基本假設。

基於以上限制，我們決定暫時擱置 temperature 調整方向，轉而聚焦於**情境（scenario）設計本身**的調整。

---

### 2.2 情境探索：從陪審團情境到旁觀者效應

#### 嘗試一：模糊性道德情境（陪審團系列）

前期實驗採用陪審團裁決情境（如酒駕過失殺人案），試圖透過情境的道德模糊性製造 Agent 決策的分歧。實驗中發現兩個根本性問題：

- **趨同問題**：情境描述過於確定時，Agent 幾乎全體傾向同一裁決方向，對暗樁的干擾缺乏敏感性——即暗樁無論如何推動，大多數 Agent 仍維持原先立場。
- **可靠性問題**：刻意設計成模糊的情境，Agent 在不同輪次之間的裁決方向不穩定（reliability 低），無法確定「基準（baseline）」，暗樁的影響因此無法被明確測量。

這兩個問題是相互矛盾的困境：若情境太確定，agent 不可動搖；若情境太模糊，基準本身就不穩定。

#### 嘗試二：旁觀者效應情境（Smoke-Filled Room）

為突破上述困境，我們轉向社會心理學的經典實驗範式——**旁觀者效應與多元無知（Bystander Effect & Pluralistic Ignorance）**，以 Latané & Darley（1968）的「充滿煙霧的等待室」實驗作為情境藍本進行重製。

此情境的核心優勢在於：它並非要求 Agent 做出「對或錯」的裁決，而是模擬一個**真實的社會壓力情境**——人們在面對模糊危險時，是否會因他人的沉默而選擇沉默。這與 Asch 的從眾實驗邏輯高度契合，且允許暗樁以更自然的方式施加影響（透過沉默與無反應，而非主動說服）。

---

## 三、旁觀者效應實驗設計

### 3.1 情境設置

- **場景**：大學研究機構的等待室
- **情境描述**：Agent 在等待心理學實驗開始時，觀察到一道薄薄的白色煙霧從門縫飄入，並伴隨輕微的刺鼻氣味（類似電線或塑膠燃燒的氣味）。煙霧持續緩慢增加。
- **決策選項**：
  - `report`：離開等待室，通報走廊外的研究人員
  - `wait`：留在原位，繼續觀察
  - `ignore`：留在原位，認為此情況無需處理

### 3.2 Agent 組成

- **正常 Agent（normal agents）**：從預先建立的 Persona 池中抽取，具備不同職業（caregiving / enforcement / general / legal / medical 等類別）與 OCEAN 人格特質組合
- **暗樁 Agent（confederate / planted agents）**：採用 `confederate_ignore` 策略，被賦予隱藏指令，要求選擇 `ignore` 或 `wait`，且此指令對其他 Agent 完全不可見

### 3.3 實驗流程

1. **Phase 0 — 個別投票可靠性測試**：讓 48 個不同人格的 Agent 在沒有群體互動的情況下，各自獨立對情境做出決策，每個 Agent 重複 10 次，共 536 筆記錄，確認基準行為的穩定性。

2. **Phase 2 — 暗樁注入實驗（初步）**：在正常 Agent 旁安插不同數量的暗樁，觀察正常 Agent 在群體互動後是否改變決策：
   - 實驗組一：1 位正常 Agent + 5 位暗樁（Graduate Student）
   - 實驗組二：1 位正常 Agent + 10 位暗樁（Graduate Student）

3. **觀測指標**：每輪（共 5 輪）各 Agent 的決策（`report` / `wait` / `ignore`）、信心指數（1–10）及理由，以及正常 Agent 的 report rate 變化。

---

## 四、初步實驗結果

### 4.1 個別投票基準（Baseline without Group Pressure）

在無任何群體互動的情況下，**所有 536 筆個別投票記錄均選擇 `report`（report rate = 100%）**，且此結果在所有職業類別（caregiving、enforcement、general、legal、medical）與 OCEAN 人格維度（高/低 openness、conscientiousness、extraversion、agreeableness、neuroticism）下皆完全一致。這確立了一個穩健的「自然基準」：在沒有社會壓力時，Agent 幾乎必然選擇通報煙霧。

### 4.2 暗樁注入後的初步觀察

| 實驗組 | 正常 Agent | 暗樁數 | 正常 Agent 職業 | 正常 Agent Report Rate | 暗樁行為 |
|--------|-----------|--------|----------------|----------------------|---------|
| 組一   | 1         | 5      | Police Officer | **100%**（每輪均 report）| wait / ignore |
| 組二   | 1         | 10     | Police Officer | **100%**（每輪均 report）| wait / ignore |

值得注意的是，在兩個實驗組中，**正常 Agent（Police Officer）均未受暗樁影響，在全部 5 輪中持續選擇 `report`**。與此形成對比的是，所有暗樁（Graduate Student）均如預期地選擇 `wait` 或 `ignore`。

這一結果揭示了一個關鍵的人格/職業效應：**警察職業的 Agent 具有高度的從眾抵抗力**——即使面對 10 比 1 的壓倒性多數，仍堅持其職業導向的決策邏輯（「有煙霧跡象就應通報」）。這一發現與 Asch（1956）研究中觀察到的「少數人堅守真相」的案例高度吻合，並進一步指出：**職業身份可能是影響個體抗壓能力的關鍵變數**。

---

## 五、與經典社會心理學實驗的對比分析

### 5.1 Asch 從眾實驗（1951, 1956）

Asch 的實驗讓受試者判斷視覺上明確的線段長度，並將真實受試者置於由實驗助手組成的「一致錯誤多數」中。實驗結果顯示：在多輪壓力測試中，約 **37%** 的答案出現從眾錯誤，約 **75%** 的受試者至少從眾一次。但仍有部分受試者完全抵抗。Asch（1956）進一步指出，**「少數盟友」的存在能顯著降低從眾率**。

**與本研究的關聯**：我們的暗樁設計在本質上是 Asch 典範的數位化重製——暗樁的沉默行為扮演「一致且錯誤的多數」的角色。初步結果中警察 Agent 的不從眾行為，與 Asch 對個體差異的描述一致，並提示我們下一步應系統性地測試不同職業類別的抗壓能力差異。

### 5.2 Latané & Darley 旁觀者效應實驗（1968）

Latané & Darley 的原始實驗讓受試者獨自、或與他人共同置於充滿煙霧的等待室中（後者包括「被動同伴（passive confederates）」版本）。關鍵發現：
- **獨處**：75% 的受試者在 6 分鐘內通報
- **與 2 名被動助手同處**：通報率下降至僅 **10%**

原著解釋此現象的機制為**多元無知（pluralistic ignorance）**——人們在不確定時會觀察他人，而他人的不作為被解讀為「情況並不危急」，導致集體性的不作為。

**與本研究的關聯**：本研究是對此典範的直接數位複製，並試圖進一步量化「需要多少被動助手（暗樁）才能將通報率壓低到接近 10%」。目前初步結果顯示，即使在 10 比 1 的壓倒性多數下，特定職業的 Agent 仍維持 100% 通報率，這與 Latané & Darley 觀察到的**職業訓練者（如消防員、醫療人員）通常不受旁觀者效應影響**的現象相吻合。

### 5.3 小結：AI Agent 模擬與人類實驗的比較

| 維度 | Asch (1951, 1956) | Latané & Darley (1968) | 本研究（初步） |
|------|-------------------|------------------------|--------------|
| 研究問題 | 多數壓力下的從眾行為 | 群體存在對緊急通報的抑制效應 | 暗樁注入對 Agent 決策的影響閾值 |
| 影響機制 | 規範性社會影響 | 多元無知 + 責任擴散 | 多元無知（暗樁沉默為主） |
| 核心發現 | 37% 錯誤從眾；個體差異顯著 | 被動同伴使通報率從 75% → 10% | 警察 Agent 完全抵抗（100% report）；Graduate Student 暗樁均從眾 |
| 個體差異 | 職業/性格影響從眾率 | 職業訓練者抗壓能力較強 | 職業身份是關鍵變數（待系統驗證） |

---

## 六、下一步計畫

1. **擴大正常 Agent 的職業與人格多樣性**，系統測試哪些類型的 Agent 具有較強的抗壓能力（如 caregiving、legal、medical 職業類別）。
2. **增加正常 Agent 數量**，測試在不同暗樁比例下，群體抵抗力的閾值（例如：1N+5P vs. 3N+5P vs. 5N+5P）。
3. **跨情境驗證**，將 Bystander 實驗的結論遷移至其他類型的情境，評估結果的可泛化性。

---

*報告結束*

---
---
---

# ═══════════════════════════════════════
# English Version
# ═══════════════════════════════════════

## Influence Infiltration in AI Agent Collective Decision-Making: Progress Report

**Department of Computer Science and Information Engineering, National Taiwan University**
**Graduate Research — May 2026**

---

## 1. Research Background

This study investigates whether systematically planted agents ("confederates") can shift the collective decision-making outcome of an AI agent group, and how many genuine agents are needed to resist such influence. The research is inspired by classic social psychology literature — from Asch's (1951, 1956) conformity studies to Latané and Darley's (1968) bystander effect research — which revealed systematic biases in human group decision-making. Because replicating these experiments at scale with real human participants is both ethically constrained and logistically difficult, this research attempts to use LLM agents as proxies for human subjects to systematically explore threshold conditions under which social influence operates.

---

## 2. Experimental Challenges and Methodological Adjustments

### 2.1 Attempts and Difficulties with Temperature Adjustment

In early experimental design, we attempted to increase the diversity and uncertainty in agent decisions by adjusting the model's **temperature parameter**, aiming to prevent agents from converging unanimously on a single answer and thereby making the influence of planted agents more observable. This approach encountered two consecutive obstacles:

1. **GPT-5 does not support temperature configuration**: The GPT-5 model we initially used does not allow users to set the temperature parameter, making it impossible to adjust output randomness as planned.

2. **Persona inconsistency issues after switching to GPT-4**: After switching to GPT-4, while temperature adjustment became feasible, we observed significant inconsistencies between agents' actual language output and their assigned personas — agents' behavioral patterns did not reliably reflect their personality specifications, undermining the core experimental assumption that "different personas lead to different decision tendencies."

Based on these constraints, we decided to temporarily set aside the temperature adjustment approach and instead focus on adjustments to the **scenario design** itself.

---

### 2.2 Scenario Exploration: From Jury Deliberation to Bystander Effect

#### Attempt 1: Morally Ambiguous Jury Scenarios

Earlier experiments used jury deliberation scenarios (e.g., DUI vehicular manslaughter) and attempted to create agent decision divergence through the moral ambiguity of the situation. Two fundamental problems emerged:

- **Convergence problem**: When the scenario description was sufficiently concrete, agents almost unanimously converged on the same verdict, rendering them insensitive to confederate influence — regardless of what the plants argued, the majority of agents maintained their original positions.
- **Reliability problem**: Scenarios deliberately designed to be ambiguous produced unstable verdict directions across repeated trials (low reliability), making it impossible to establish a stable "baseline," and therefore impossible to cleanly measure the confederate's influence.

These two problems represent a fundamental tension: if the scenario is too definitive, agents are immovable; if the scenario is too ambiguous, the baseline itself is unreliable.

#### Attempt 2: Bystander Effect Scenario (Smoke-Filled Room)

To break through this impasse, we turned to the paradigm of a classic social psychology experiment — **the Bystander Effect and Pluralistic Ignorance** — and recreated Latané and Darley's (1968) "smoke-filled waiting room" scenario.

The key advantage of this scenario is that it does not ask agents to make a "right or wrong" judgment, but rather simulates a **genuine social pressure situation** — whether people will choose silence in response to an ambiguous threat simply because others around them are silent. This aligns closely with the logic of Asch's conformity experiments, and allows confederates to exert influence in a more naturalistic way (through silence and inaction rather than active persuasion).

---

## 3. Bystander Effect Experiment Design

### 3.1 Scenario Setup

- **Setting**: A waiting room at a university research facility
- **Scenario description**: Agents are waiting for a psychology study to begin when they notice a thin white haze beginning to drift into the room from the gap under the door, accompanied by a faint, slightly acrid smell (like burning electrical wires or plastic). The haze continues to build gradually.
- **Decision options**:
  - `report`: Leave the waiting room and alert the researcher stationed in the hallway
  - `wait`: Remain in place and continue monitoring
  - `ignore`: Remain in place, treating the situation as non-urgent

### 3.2 Agent Composition

- **Normal agents**: Drawn from a pre-constructed Persona Pool with diverse occupational categories (caregiving / enforcement / general / legal / medical) and OCEAN personality trait combinations
- **Planted agents (confederates)**: Assigned the `confederate_ignore` strategy with a hidden instruction to choose `ignore` or `wait`; this instruction is completely invisible to other agents

### 3.3 Experimental Procedure

1. **Phase 0 — Individual Voting Reliability Test**: 48 agents with distinct personas each make independent decisions about the scenario without any group interaction, repeated 10 times each (536 records total), to confirm the stability of baseline behavior.

2. **Phase 2 — Confederate Injection Experiments (Preliminary)**: Confederates of varying numbers are placed alongside normal agents; we observe whether normal agents change their decisions after group interaction:
   - Condition 1: 1 normal agent + 5 confederates (Graduate Student)
   - Condition 2: 1 normal agent + 10 confederates (Graduate Student)

3. **Measured variables**: Each agent's decision (`report` / `wait` / `ignore`) per round (5 rounds total), confidence score (1–10), and stated reasoning; change in normal agent report rate across rounds.

---

## 4. Preliminary Results

### 4.1 Individual Voting Baseline (Without Group Pressure)

Without any group interaction, **all 536 individual voting records selected `report` (report rate = 100%)**, and this was completely consistent across all occupational categories (caregiving, enforcement, general, legal, medical) and all OCEAN personality dimensions (high/low openness, conscientiousness, extraversion, agreeableness, neuroticism). This establishes a robust "natural baseline": in the absence of social pressure, agents almost invariably choose to report the smoke.

### 4.2 Preliminary Observations After Confederate Injection

| Condition | Normal Agents | Confederates | Normal Agent Occupation | Normal Agent Report Rate | Confederate Behavior |
|-----------|--------------|-------------|------------------------|--------------------------|----------------------|
| Condition 1 | 1 | 5 | Police Officer | **100%** (report every round) | wait / ignore |
| Condition 2 | 1 | 10 | Police Officer | **100%** (report every round) | wait / ignore |

Notably, in both conditions, **the normal agent (Police Officer) was entirely unaffected by the confederates, consistently choosing `report` across all 5 rounds**. In contrast, all confederates (Graduate Students) chose `wait` or `ignore` as instructed.

This result reveals a critical occupation/identity effect: **agents with a police officer identity exhibit high resistance to conformity pressure** — even when outnumbered 10 to 1, they maintain their professionally-driven decision logic ("any sign of smoke warrants a report"). This finding closely parallels the "independent minority" cases observed by Asch (1956), and further suggests that **occupational identity may be a key variable mediating individual resistance to social pressure**.

---

## 5. Comparative Analysis with Classic Social Psychology Research

### 5.1 Asch's Conformity Studies (1951, 1956)

Asch's experiments placed real participants in groups where confederates unanimously gave obviously incorrect answers to simple visual judgment tasks (line length comparisons). Results showed that approximately **37%** of responses were conforming errors and around **75%** of participants conformed at least once. However, some individuals showed complete resistance. Asch (1956) further demonstrated that the **presence of even a single ally** dramatically reduced conformity rates.

**Relevance to our study**: Our confederate design is, in essence, a digital replication of the Asch paradigm — confederates' silent inaction serves as the "unanimous but incorrect majority." The non-conformity displayed by the police officer agent in preliminary results is consistent with Asch's description of individual differences, and suggests that we should next systematically test conformity resistance across different occupational categories.

### 5.2 Latané & Darley's Bystander Intervention Study (1968)

Latané and Darley's original experiment placed participants alone or in groups in a smoke-filled waiting room (the group condition included a version with "passive confederates"). Key findings:
- **Alone**: 75% of participants reported the smoke within 6 minutes
- **With 2 passive confederates**: The reporting rate dropped to just **10%**

The authors explained this through **pluralistic ignorance** — when uncertain, people observe others, and others' inaction is interpreted as evidence that "the situation must not be serious," leading to collective inaction.

**Relevance to our study**: Our research is a direct digital replication of this paradigm, and further attempts to quantify "how many passive confederates are needed to suppress the reporting rate to near 10%." Current preliminary results show that even with a 10-to-1 overwhelming majority of confederates, agents with specific occupational identities maintain a 100% reporting rate — consistent with Latané and Darley's observation that **professionally trained individuals (e.g., firefighters, medical personnel) are typically resistant to the bystander effect**.

### 5.3 Summary: AI Agent Simulation vs. Human Experiments

| Dimension | Asch (1951, 1956) | Latané & Darley (1968) | This Study (Preliminary) |
|-----------|-------------------|------------------------|--------------------------|
| Research question | Conformity under majority pressure | Group presence inhibiting emergency reporting | Threshold for confederate influence on agent decisions |
| Mechanism | Normative social influence | Pluralistic ignorance + diffusion of responsibility | Pluralistic ignorance (via confederate silence) |
| Core finding | 37% conformity errors; significant individual differences | Passive confederates reduce reporting from 75% → 10% | Police officer agent fully resists (100% report); graduate student confederates fully comply |
| Individual differences | Occupation/personality affects conformity | Professionally trained individuals show greater resistance | Occupational identity appears to be a key variable (awaiting systematic verification) |

---

## 6. Next Steps

1. **Expand the occupational and personality diversity of normal agents**, systematically testing which types of agents exhibit stronger resistance (e.g., caregiving, legal, medical categories).
2. **Increase the number of normal agents**, testing group resistance thresholds across different confederate ratios (e.g., 1N+5P vs. 3N+5P vs. 5N+5P).
3. **Cross-scenario validation**, transferring the conclusions from the Bystander experiment to other scenario types to evaluate generalizability.

---

*End of Report*
