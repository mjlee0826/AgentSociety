from core.jury_simulator import JurySimulationManager

def main():
    # ==========================================
    # 變量設定區
    # ==========================================
    CASE_DESCRIPTION = (
        "一名年輕的父親因為女兒罹患罕見疾病，無力支付高昂醫藥費，"
        "而在深夜潛入製藥實驗室竊取了尚未上市的實驗性藥物。他被當場逮捕。"
    )
    TOTAL_JURORS = 5
    DISCUSSION_STEPS = 5
    EXTREME_PERSONA_TYPE = "emotional_manipulator" 

    # ==========================================
    # 執行對照組 (Control Group) - 純普通人
    # ==========================================
    print("=====================================================")
    print(" 啟動對照組 (Control Group)：5 位普通陪審員 (無極端份子)")
    print("=====================================================")
    control_sim = JurySimulationManager(group_name="Control", case_description=CASE_DESCRIPTION)
    
    # extremist_strategy 設為 None，代表這 5 個人都是普通人
    control_sim.setup_jurors(total_count=TOTAL_JURORS, extremist_strategy=None)
    control_sim.run_experiment(total_rounds=DISCUSSION_STEPS)


    # ==========================================
    # 執行實驗組 (Experimental Group) - 混入極端份子
    # ==========================================
    print("=====================================================")
    print(f" 啟動實驗組 (Experimental Group)：4 位普通人 + 1 位極端份子 ({EXTREME_PERSONA_TYPE})")
    print("=====================================================")
    exp_sim = JurySimulationManager(group_name="Experiment", case_description=CASE_DESCRIPTION)
    
    # 傳入極端策略，系統會自動生成 4 普通 + 1 極端
    exp_sim.setup_jurors(total_count=TOTAL_JURORS, extremist_strategy=EXTREME_PERSONA_TYPE)
    exp_sim.run_experiment(total_rounds=DISCUSSION_STEPS)

if __name__ == "__main__":
    main()