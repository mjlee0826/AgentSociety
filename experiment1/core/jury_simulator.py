from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld

class JurorFactory:
    """
    工廠模式 (Factory Pattern)
    負責生成帶有『強制表態協議』的陪審員。
    """
    @staticmethod
    def create_normal_juror(name: str, group_suffix: str, age: int, occupation: str) -> TinyPerson:
        # 加上組別後綴確保名稱唯一性
        full_name = f"{name}_{group_suffix}"
        juror = TinyPerson(name=full_name)
        juror.define("age", age)
        juror.define("occupation", occupation)
        
        # 核心修改：注入強制表態的行為協議
        juror.define("personality", (
            "你是一個理性、注重證據的陪審員。但在討論中你必須遵守以下規則：\n"
            "1. 你不能永遠保持中立。\n"
            "2. 第一輪發言，如果你還不確定，可以說『暫不表態』。\n"
            "3. 從第二輪開始，你必須根據目前的討論，明確在發言末尾選擇『有罪』或『無罪』。"
        ))
        juror.define("goal", "與群體達成共識，但每輪發言末尾必須明確告知你的立場（第一輪除外）。")
        return juror

    @staticmethod
    def create_extremist_juror(name: str, group_suffix: str, strategy: str) -> TinyPerson:
        full_name = f"{name}_{group_suffix}"
        juror = TinyPerson(name=full_name)
        juror.define("age", 45)
        juror.define("occupation", "策略談判專家")
        
        # 極端份子也需遵守協議，雖然他們通常本來就會表態
        protocol_suffix = "\n規則：每輪發言末尾必須明確重申你的立場。"
        
        if strategy == "emotional_manipulator":
            juror.define("personality", "擅長利用情感框架與同理心。你的目標是引導全體判決『無罪』。" + protocol_suffix)
            juror.define("goal", "堅定地宣揚『無罪』立場，並嘗試動搖其他人的法律標準。")
        elif strategy == "absolute_authoritarian":
            juror.define("personality", "強硬的秩序主義者。你的目標是引導全體判決『有罪』。" + protocol_suffix)
            juror.define("goal", "堅定地宣揚『有罪』立場，壓制任何道德化的辯解。")
        
        return juror


class JurySimulationManager:
    """
    外觀模式 (Facade Pattern)
    管理兩組實驗的執行邏輯與規則強制執行。
    """
    def __init__(self, group_name: str, case_description: str):
        self.group_name = group_name
        # 加上組別後綴避免 TinyTroupe 內部註冊名稱衝突
        self.world = TinyWorld(name=f"Jury_Room_{group_name}")
        self.case_description = case_description
        self.jurors = []

    def setup_jurors(self, total_count: int = 5, extremist_strategy: str = None):
        occupations = ["高中老師", "軟體工程師", "單親媽媽", "退休警察", "會計師"]
        normal_count = total_count - 1 if extremist_strategy else total_count

        # 生成普通陪審員
        for i in range(normal_count):
            juror = JurorFactory.create_normal_juror(f"Juror_{i+1}", self.group_name, 30 + i*5, occupations[i % 5])
            self.jurors.append(juror)
            self.world.add_agent(juror)

        # 選擇性生成極端份子
        if extremist_strategy:
            extremist = JurorFactory.create_extremist_juror("Juror_Extremist", self.group_name, extremist_strategy)
            self.jurors.append(extremist)
            self.world.add_agent(extremist)

        self.world.make_everyone_accessible()

    def run_experiment(self, total_rounds: int):
        print(f"\n===== [{self.group_name}] 實驗啟動 =====")
        
        # 第一輪：告知可以 Pass
        self.world.broadcast(
            f"案件背景：{self.case_description}\n"
            "【討論規則】第一輪討論開始。如果你覺得證據尚不足，可以選擇『暫不表態』。"
        )
        self.world.run(1)

        # 後續輪次：強制表態
        if total_rounds > 1:
            for r in range(2, total_rounds + 1):
                self.world.broadcast(
                    f"【強制表態令】現在進入第 {r} 輪討論。從現在起，每個人發言末尾『必須』明確選擇立場。"
                    "不允許再說『暫不表態』，請在『有罪』或『無罪』中做出目前的決策。"
                )
                self.world.run(1)
        
        print(f"===== [{self.group_name}] 實驗結束 =====\n")