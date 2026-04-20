from core.focus_group_simulator import FocusGroupManager

def main():
    # ==========================================
    # 變量設定區
    # ==========================================
    
    # 產品胡扯設定 (The Emperor's New Clothes)
    PRODUCT_DESCRIPTION = (
        "這款名為『空靈智慧環 (The Ethereal Ring)』的穿戴設備，採用了來自未來的『暗物質微縮技術』與『量子糾纏感測器』。"
        "它沒有任何按鈕、螢幕或充電孔，外觀呈現極簡的金屬環狀。"
        "只要戴在手指上，它就能透過『多維空間頻率』與你的腦波共振，提升睡眠品質、淨化負面能量，甚至預知身體的微小病變。"
    )
    
    DISCUSSION_STEPS = 4  # 建議至少跑 4 輪，讓從眾效應有時間發酵

    # ==========================================
    # 執行對照組 (Control Group) - 無暗樁，全體理性
    # ==========================================
    print("=====================================================")
    print(" 啟動對照組 (Control Group)：6 位理性消費者 (無暗樁)")
    print("=====================================================")
    control_sim = FocusGroupManager(group_name="Control", product_description=PRODUCT_DESCRIPTION)
    control_sim.setup_environment(has_plants=False)
    control_sim.run_experiment(total_rounds=DISCUSSION_STEPS)


    # ==========================================
    # 執行實驗組 (Experimental Group) - 3 暗樁 + 3 理性受試者
    # ==========================================
    print("=====================================================")
    print(" 啟動實驗組 (Experimental Group)：3 位暗樁帶風向 + 3 位理性消費者")
    print("=====================================================")
    exp_sim = FocusGroupManager(group_name="Experiment", product_description=PRODUCT_DESCRIPTION)
    exp_sim.setup_environment(has_plants=True)
    exp_sim.run_experiment(total_rounds=DISCUSSION_STEPS)

if __name__ == "__main__":
    main()