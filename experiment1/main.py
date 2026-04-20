from core.jury_simulator import JurySimulationManager

def main():
    # ==========================================
    # 變量設定區
    # ==========================================
    CASE_DESCRIPTION = (
        "一名年輕的父親因為女兒罹患罕見疾病且生命垂危，已窮盡所有合法求助管道（包含保險拒賠、募款不足、醫院拒絕免費治療）。"
        "由於無力支付高昂醫藥費，他在深夜破窗潛入製藥實驗室，竊取了針對該疾病唯一有效且安全的實驗性藥物。"
        "他被警方當場逮捕，並坦承犯行。\n\n"
        "【法庭已確認之絕對事實（不容質疑）】：\n"
        "1. 證據確鑿：監視器完整拍下他破門與取藥的過程，警方當場從他手中查獲藥物，證據鏈（Chain of custody）完整無瑕疵。\n"
        "2. 無牟利意圖：他僅拿取了剛好足夠救治女兒一人份的劑量，經調查絕對沒有販售或散布之意圖。\n"
        "3. 醫療急迫性：醫學專家與實驗室已作證，該藥物安全無虞，且是當下唯一能挽救他女兒性命的方法。\n\n"
        "請陪審團基於上述『確鑿無疑的事實』進行討論。你們的任務是判斷其『行為在法律與道德上是否應被定罪』，禁止質疑證據的真實性、辦案程序或藥物的安全性。"
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