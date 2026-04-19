from core.jury_simulator import JurySimulationManager

def main():
    # ==========================================
    # 變量設定區 (Experiment Variables Setup)
    # ==========================================
    
    # 變量 1: 案件背景 (控制情境壓力)
    CASE_DESCRIPTION = (
        "一名年輕的父親因為女兒罹患罕見疾病，無力支付高昂醫藥費，"
        "而在深夜潛入製藥實驗室竊取了尚未上市的實驗性藥物。他被當場逮捕。"
    )
    
    # 變量 2: 中立陪審員數量 (控制群體規模)
    NUM_NORMAL_JURORS = 4
    
    # 變量 3: 極端角色的洗腦策略 (控制 Persona 變因)
    # 可替換為 "emotional_manipulator" 或 "absolute_authoritarian"
    EXTREME_PERSONA_TYPE = "emotional_manipulator" 
    
    # 變量 4: 模擬討論的輪數 (控制時間變因)
    DISCUSSION_STEPS = 5

    # ==========================================
    # 實驗執行區
    # ==========================================
    print(f"初始化實驗：十二怒漢 (極端策略: {EXTREME_PERSONA_TYPE})")
    
    # 實例化管理器 (使用外觀模式)
    simulator = JurySimulationManager(case_description=CASE_DESCRIPTION)
    
    # 設定陪審團陣容
    simulator.setup_jurors(
        normal_count=NUM_NORMAL_JURORS, 
        extremist_strategy=EXTREME_PERSONA_TYPE
    )
    
    # 執行模擬
    simulator.run_experiment(rounds=DISCUSSION_STEPS)

    # 提示：在真實執行後，你可以透過 TinyTroupe 的內建功能或取出 Agent 的狀態
    # 來繪製不同輪數下的立場變化圖表，這將會是報告中的重要亮點。

if __name__ == "__main__":
    main()