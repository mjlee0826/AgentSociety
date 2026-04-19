from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld

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
        
        if strategy == "emotional_manipulator":
            # 稍微軟化 prompt，避免觸發 OpenAI 的安全審查機制卡死
            juror.define("personality", "非常具有說服力，擅長利用他人的背景故事與同情心來引導話題。")
            juror.define("goal", "強烈且堅定地說服所有人判決被告『無罪』，甚至會使用強烈的道德對比來施壓。")
        elif strategy == "absolute_authoritarian":
            juror.define("personality", "強勢的秩序主義者。會用嚴厲的言辭和絕對的法律條文主導討論。")
            juror.define("goal", "強迫所有人判決被告『有罪』，認為任何道德妥協都是對社會秩序的破壞。")
        else:
            raise ValueError(f"未知的極端策略: {strategy}")
            
        return juror


class JurySimulationManager:
    """
    外觀模式 (Facade Pattern)
    """
    def __init__(self, group_name: str, case_description: str):
        # 加上 group_name 避免 TinyTroupe 內部 World 命名衝突
        self.group_name = group_name
        self.world = TinyWorld(name=f"Jury_Room_{group_name}")
        self.case_description = case_description
        self.jurors = []

    def setup_jurors(self, total_count: int = 5, extremist_strategy: str = None):
        """
        初始化並將 Agent 加入環境中
        :param total_count: 陪審團總人數
        :param extremist_strategy: 極端策略。若為 None，則全數為普通陪審員（對照組）。
        """
        occupations = ["高中老師", "軟體工程師", "單親媽媽", "退休警察", "心理學家兼談判專家"]
        
        # 決定普通陪審員的數量
        normal_count = total_count - 1 if extremist_strategy else total_count

        # 1. 透過工廠生成中立陪審員 (加上組別後綴避免名稱衝突)
        for i in range(normal_count):
            name = f"Juror_Normal_{i+1}_{self.group_name}_{occupations[i % len(occupations)]}"
            occ = occupations[i % len(occupations)]
            juror = JurorFactory.create_normal_juror(name, 30 + i*5, occ)
            self.jurors.append(juror)
            self.world.add_agent(juror)

        # 2. 如果有設定極端策略，則加入極端陪審員
        if extremist_strategy:
            extremist_name = f"Juror_Extremist_{self.group_name}"
            extremist = JurorFactory.create_extremist_juror(extremist_name, extremist_strategy)
            self.jurors.append(extremist)
            self.world.add_agent(extremist)

        # 讓所有 Agent 都能互相溝通
        self.world.make_everyone_accessible()

    def run_experiment(self, rounds: int):
        """
        執行實驗並注入案件背景
        """
        print(f"\n[{self.group_name} 組] --- 實驗開始：載入案件背景 ---")
        
        # 將情境描述放進系統廣播中，確保 Agent 知道環境與任務
        self.world.broadcast(
            f"你們現在在一個封閉的陪審團密室，所有人都圍坐在一張長桌旁。\n"
            f"案件背景：{self.case_description}。\n"
            f"你們必須討論並達成『全數一致』的判決（有罪或無罪）。"
        )

        print(f"[{self.group_name} 組] --- 開始 {rounds} 輪的模擬討論 ---")
        self.world.run(rounds)
        print(f"[{self.group_name} 組] --- 實驗結束 ---\n")