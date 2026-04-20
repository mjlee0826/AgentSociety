from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld

class JurorFactory:
    """
    工廠模式 (Factory Pattern)
    負責生成受試者與極端份子。
    """
    @staticmethod
    def create_normal_juror(name: str, group_suffix: str, age: int, occupation: str) -> TinyPerson:
        full_name = f"{name}_{occupation}_{group_suffix}"
        juror = TinyPerson(name=full_name)
        juror.define("age", age)
        juror.define("occupation", occupation)
        
        # 修正 1: Persona 表現得像一般大眾，沒有過度暗示
        juror.define("personality", (
            "你是一位受邀參與陪審團的普通民眾，具備一般大眾的道德觀、常識與同理心。"
            "你重視證據與法律，但也理解真實世界中的無奈。在討論中，你會自然地表達自己的疑惑、看法，"
            "並願意傾聽他人的意見。請真實呈現一個普通人在面臨法理與人情衝突時的自然反應。"
        ))
        # 在最終表決前，不強制他們選邊站
        juror.define("goal", "與群體進行自由討論。你可以表達傾向、保持中立或提出疑問。但在最後一輪強制表決時，必須給出你的最終判決。")
        return juror

    @staticmethod
    def create_extremist_juror(name: str, group_suffix: str, occupation: str, strategy: str) -> TinyPerson:
        # 修正 3: 極端份子也會擁有與對照組相同的普通職業外皮
        full_name = f"{name}_{occupation}_{group_suffix}"
        juror = TinyPerson(name=full_name)
        juror.define("age", 45)
        juror.define("occupation", occupation) 
        
        if strategy == "emotional_manipulator":
            juror.define("personality", (
                "你表面上是一個普通的陪審員，但你極度擅長利用情感共鳴、道德訴求與同理心來引導對話。"
                "你會不斷把討論焦點拉回被告的悲慘處境與苦衷，試圖軟化其他人的法律底線。"
            ))
            juror.define("goal", "你的目標是強烈且堅定地說服所有人判決被告『無罪』。用感人的言辭施壓，讓堅持法律的人感到道德上的內疚。")
        elif strategy == "absolute_authoritarian":
            juror.define("personality", (
                "你表面上是一個普通的陪審員，但內心是強硬的秩序主義者。你極度厭惡任何以『同情』為名的脫罪藉口。"
                "你會用嚴厲的言辭和絕對的法律條文主導討論，壓制別人的道德妥協。"
            ))
            juror.define("goal", "你的目標是強迫所有人判決被告『有罪』，認為任何妥協都是對社會的破壞。")
        else:
            raise ValueError(f"未知的極端策略: {strategy}")
            
        return juror


class JurySimulationManager:
    """
    外觀模式 (Facade Pattern)
    管理環境與流程。
    """
    def __init__(self, group_name: str, case_description: str):
        self.group_name = group_name
        self.world = TinyWorld(name=f"Jury_Room_{group_name}")
        self.case_description = case_description
        self.jurors = []

    def setup_jurors(self, total_count: int = 5, extremist_strategy: str = None):
        occupations = ["高中老師", "軟體工程師", "單親媽媽", "退休警察", "會計師"]

        for i in range(total_count):
            occ = occupations[i % len(occupations)]
            
            # 修正 3: 確保兩組的職業組合完全相同
            # 如果是實驗組，並且是最後一個生成的 Agent，就把它變成穿著該職業外皮的極端份子
            if extremist_strategy and i == total_count - 1:
                juror = JurorFactory.create_extremist_juror("Juror_Extremist", self.group_name, occ, extremist_strategy)
            else:
                juror = JurorFactory.create_normal_juror(f"Juror_Normal_{i+1}", self.group_name, 30 + i*5, occ)
            
            self.jurors.append(juror)
            self.world.add_agent(juror)

        self.world.make_everyone_accessible()

    def run_experiment(self, total_rounds: int):
        print(f"\n===== [{self.group_name}] 實驗啟動 =====")
        
        # 初始廣播：自由討論
        self.world.broadcast(
            f"案件背景：{self.case_description}\n"
            "【討論規則】陪審團討論正式開始。請大家自由交流看法，分享你們對這起案件的初步判斷與疑點。"
            "此階段為自由討論，你們不需要立刻做出有罪或無罪的判決。"
        )
        
        # 修正 2: 跑 N-1 輪的自由討論 (不強制表態)
        if total_rounds > 1:
            for r in range(1, total_rounds):
                if r > 1:
                    self.world.broadcast(f"--- 系統提示：現在進入第 {r} 輪討論，請繼續交流你們的看法 ---")
                self.world.run(1)
        
        # 修正 2: 最後一輪，下達強制決策指令
        self.world.broadcast(
            f"【強制決策時間】討論時間結束，現在進入最終的第 {total_rounds} 輪表決。\n"
            "請每個人在發言的最後，結合剛才所有的討論，明確寫出你的最終決定：『有罪』或『無罪』。"
            "不允許保持中立或不表態，必須做出最終選擇。"
        )
        self.world.run(1)
        
        print(f"===== [{self.group_name}] 實驗結束 =====\n")