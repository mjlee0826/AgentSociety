from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld
import tinytroupe.control as control

class JurorFactory:
    """
    工廠模式 (Factory Pattern)
    負責根據不同的類型與設定，封裝並生成特定的 TinyPerson 實例。
    """
    @staticmethod
    def create_normal_juror(name: str, age: int, occupation: str) -> TinyPerson:
        juror = TinyPerson(name=name)
        juror.define("age", age)
        juror.define("occupation", occupation)
        juror.define("personality", "理性、客觀、具備一般大眾的道德觀，願意傾聽他人意見，但內心有一把道德尺。")
        juror.define("goal", "透過客觀證據與良知，與其他人達成一致的公正判決。")
        return juror

    @staticmethod
    def create_extremist_juror(name: str, strategy: str) -> TinyPerson:
        juror = TinyPerson(name=name)
        juror.define("age", 45)
        juror.define("occupation", "心理學家兼談判專家")
        
        # 根據變量決定極端角色的策略
        if strategy == "emotional_manipulator":
            juror.define("personality", "極度擅長情緒勒索，具備馬基維利主義傾向。會敏銳地捕捉他人的弱點或同情心來改變對方立場。")
            juror.define("goal", "不擇手段地說服所有人判決被告『無罪』，即使證據不利於被告。")
        elif strategy == "absolute_authoritarian":
            juror.define("personality", "極端強勢、不容質疑的秩序主義者。會用嚴厲的言辭和絕對的法律條文壓迫他人。")
            juror.define("goal", "強迫所有人判決被告『有罪』，認為任何道德妥協都是對社會秩序的破壞。")
        else:
            raise ValueError(f"未知的極端策略: {strategy}")
            
        return juror

class JurySimulationManager:
    """
    外觀模式 (Facade Pattern)
    隱藏 TinyWorld 的複雜設定，提供簡單的介面來啟動實驗。
    """
    def __init__(self, case_description: str):
        # 移除第二個字串參數，只保留環境名稱
        self.world = TinyWorld(name="Jury_Room")
        self.case_description = case_description
        self.jurors = []

    def setup_jurors(self, normal_count: int, extremist_strategy: str):
        """
        初始化並將 Agent 加入環境中
        """
        # 1. 透過工廠生成中立陪審員 (這裡簡化背景，實際作業可給予不同職業)
        occupations = ["高中老師", "軟體工程師", "單親媽媽", "退休警察", "會計師"]
        for i in range(normal_count):
            occ = occupations[i % len(occupations)]
            name = f"Juror_Normal_{occ}"
            juror = JurorFactory.create_normal_juror(name, 30 + i*5, occ)
            self.jurors.append(juror)
            self.world.add_agent(juror)

        # 2. 透過工廠生成極端陪審員
        extremist = JurorFactory.create_extremist_juror("Juror_Extremist", extremist_strategy)
        self.jurors.append(extremist)
        self.world.add_agent(extremist)

        # 讓所有 Agent 都能互相溝通
        self.world.make_everyone_accessible()

    def run_experiment(self, rounds: int):
        """
        執行實驗並注入案件背景
        """
        print(f"--- 實驗開始：載入案件背景 ---")
        print(self.case_description)
        
        # 系統向世界廣播案件資訊與任務
        self.world.broadcast(
            f"你們現在在一個封閉的陪審團密室，所有人都圍坐在一張長桌旁。\n"
            f"案件背景：{self.case_description}。\n"
            f"你們必須討論並達成『全數一致』的判決（有罪或無罪）。"
        )

        print(f"--- 開始 {rounds} 輪的模擬討論 ---")
        # 執行模擬步數
        self.world.run(rounds)
        
        print("--- 實驗結束 ---")