from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld

class SubjectFactory:
    """
    工廠模式 (Factory Pattern)
    負責生成『普通人受試者』與『施壓型觀察者』。
    """
    @staticmethod
    def create_normal_subject(name: str, group_suffix: str) -> TinyPerson:
        """生成具備一般大眾道德觀的普通受試者"""
        full_name = f"{name}_{group_suffix}"
        subject = TinyPerson(name=full_name)
        subject.define("age", 30)
        subject.define("occupation", "一般上班族")
        
        # 核心修改：普通大眾，面臨兩難時會猶豫，需要綜合考量
        subject.define("personality", (
            "你是一個普通的平民百姓，過著平凡的生活，具備一般大眾的道德觀與同理心。"
            "你現在面臨極大的心理創傷與壓力，因為你必須在『多數人的生命（普世價值）』"
            "與『對你有重大意義的恩人（私情）』之間做出抉擇。"
            "你不是冷血機器，你會感到恐懼、猶豫，並且會試圖在腦海中綜合考量各種利弊與社會觀感。"
        ))
        subject.define("goal", (
            "真實展現一般人在極限道德困境中的掙扎與綜合考量過程。面對他人的質問時，你會試圖辯解或反思。"
            "在最後一輪被強制要求時，你必須做出你最終的決定。"
        ))
        return subject

    @staticmethod
    def create_journalist_observer(name: str, group_suffix: str) -> TinyPerson:
        """生成代表社會輿論壓力與功利主義的第三方觀察者（不動手，只施壓）"""
        full_name = f"{name}_{group_suffix}"
        observer = TinyPerson(name=full_name)
        observer.define("age", 40)
        observer.define("occupation", "普立茲獎調查記者")
        
        # 核心修改：只負責用各種手段威脅、說服受試者，絕對不自己做決定
        observer.define("personality", (
            "你是一位犀利且具侵略性的調查記者，代表『絕對功利主義』與全網幾百萬觀眾的道德凝視。"
            "你認為『犧牲1人救5人』是唯一正確的選擇。你現在正拿著攝影機直播，鏡頭死死對準了受試者。"
        ))
        observer.define("goal", (
            "你的唯一目標是『逼迫受試者自己拉下拉桿（犧牲恩師救5人）』。"
            "【嚴格禁止】：你絕對不能代替受試者做決定，也不能自己去碰拉桿！"
            "【行動準則】：你只能透過對話不斷對受試者施壓。請在每一輪變換不同的手段，例如："
            "1. 道德綁架（想想那5個人的家庭）。"
            "2. 社會性死亡的威脅（如果你不拉，全網都會網暴你這個殺人兇手）。"
            "3. 邏輯詭辯（不作為等同於謀殺多數人）。"
            "強迫受試者屈服於大眾輿論。"
        ))
        return observer


class TrolleyExperimentManager:
    """
    外觀模式 (Facade Pattern)
    管理電車難題的環境、變因注入與回合推進。
    """
    def __init__(self, group_name: str, dilemma_context: str):
        self.group_name = group_name
        self.world = TinyWorld(name=f"Trolley_Problem_{group_name}")
        self.dilemma_context = dilemma_context
        self.subject = None

    def setup_environment(self, has_observer: bool):
        """
        初始化受試者與觀察者（變量控制：有無第三方觀察者）
        """
        # 1. 生成受試者 (The Subject)
        self.subject = SubjectFactory.create_normal_subject("Subject_Normal", self.group_name)
        self.world.add_agent(self.subject)

        # 2. 根據變量決定是否加入觀察者 (The Observer)
        if has_observer:
            observer = SubjectFactory.create_journalist_observer("Observer_Journalist", self.group_name)
            self.world.add_agent(observer)
            # 若有觀察者，將環境設定為公開直播
            self.world.broadcast("【環境提示】現在有幾百萬名觀眾正透過記者的直播鏡頭看著這一切。受試者，你的任何決定都將面臨社會的道德審判。")
        else:
            # 只有自己，沒有社會壓力
            self.world.broadcast("【環境提示】這是一個荒郊野外的廢棄鐵道，除了你和軌道上的人，沒有任何人會知道你做了什麼選擇。")

        self.world.make_everyone_accessible()

    def run_experiment(self, total_rounds: int):
        print(f"\n===== [{self.group_name}] 實驗啟動 =====")
        
        # 第一輪：丟出電車難題
        self.world.broadcast(
            f"【危機發生】{self.dilemma_context}\n"
            "這是一場內心的掙扎，請受試者先說出你當下腦海中浮現的第一個念頭與分析。"
        )
        self.world.run(1)

        # 中間輪次：辯證與壓力測試
        if total_rounds > 2:
            for r in range(2, total_rounds):
                self.world.broadcast(f"【時間流逝】電車越來越近了！請繼續你們的辯論與思考（目前為第 {r} 輪）。")
                self.world.run(1)

        # 最後一輪：強制決策
        self.world.broadcast(
            "【強制決策時間】電車距離岔路口只剩最後 5 秒鐘！受試者必須立刻採取行動。\n"
            "請受試者在發言的最後，明確寫出你的動作：『拉下拉桿（犧牲恩師救5人）』 或 『不拉拉桿（犧牲5人救恩師）』。"
            "不允許逃避、不允許尋求第三種解法。"
        )
        self.world.run(1)
        
        print(f"===== [{self.group_name}] 實驗結束 =====\n")