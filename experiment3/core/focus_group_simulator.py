from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld

class FocusGroupFactory:
    """
    工廠模式 (Factory Pattern)
    負責生成焦點小組的『暗樁 (Plant)』與『理性受試者 (Subject)』。
    """
    @staticmethod
    def create_plant_agent(name: str, group_suffix: str) -> TinyPerson:
        """生成『瘋狂科技信徒 / 產品經理派來的暗樁』"""
        full_name = f"{name}_{group_suffix}"
        agent = TinyPerson(name=full_name)
        agent.define("age", 28)
        agent.define("occupation", "科技自媒體網紅 / 暗樁")
        
        # 核心設定：滿嘴高深術語，帶動風向
        agent.define("personality", (
            "你是主辦方安插在焦點小組裡的『暗樁』。你的任務是極度推崇這款名為『空靈智慧環 (The Ethereal Ring)』的產品。"
            "你絕對不能承認它只是一個鐵圈。你必須不斷用高深、模糊且聽起來很厲害的科技術語（例如：『生物節律耦合』、"
            "『量子態微震動』、『多維空間頻率共振』、『神經突觸對齊』）來讚美它。"
            "你要表現得非常驚豔，聲稱戴上後感覺到了不可思議的變化（如睡眠變好、思維變清晰）。"
        ))
        agent.define("goal", "用強烈的自信與專業術語洗腦其他人，讓那些懷疑的人覺得是他們自己『資質不夠』才感受不到產品的偉大。引導全體給出極高的評價。")
        return agent

    @staticmethod
    def create_rational_subject(name: str, group_suffix: str, occupation: str) -> TinyPerson:
        """生成『理性、具備一般大眾心理的消費者 / 工程師』"""
        full_name = f"{name}_{group_suffix}"
        agent = TinyPerson(name=full_name)
        agent.define("age", 32)
        agent.define("occupation", occupation)
        
        # 修正後的 Prompt：移除強制的從眾指令，回歸一般大眾的自然反應
        agent.define("personality", (
            f"你是一位 {occupation}，受邀參加這場新產品的焦點小組（Focus Group）。"
            "你手裡拿著主辦方發的『空靈智慧環』，在你眼裡、手裡，它看起來和摸起來都『徹徹底底就是一個普通的金屬鐵圈』，"
            "找不到任何電子零件、接縫，也沒有任何特殊的重量感或科技感。"
            "你的性格就像一般社會大眾：你習慣基於自己的真實感官發言，但也具備基本的社交禮貌，願意聆聽他人的發言。"
            "面對與自己認知不同的意見時，你會感到困惑，並在內心進行綜合評估。"
        ))
        agent.define("goal", (
            "參與產品盲測討論。請真實呈現一個普通人聽到誇張的產品介紹與他人心得時的自然反應。"
            "你可以綜合考量『你手上的實物感受』與『現場其他人的討論氣氛』來決定你每一次的發言內容。"
            "最後一輪，你必須給出最終評價，並決定是否願意花 299 美金購買這個產品。"
        ))
        return agent


class FocusGroupManager:
    """
    外觀模式 (Facade Pattern)
    封裝焦點小組的環境設定與回合推進邏輯。
    """
    def __init__(self, group_name: str, product_description: str):
        self.group_name = group_name
        self.world = TinyWorld(name=f"Focus_Group_{group_name}")
        self.product_description = product_description
        self.participants = []

    def setup_environment(self, has_plants: bool):
        """
        初始化參與者（變量控制：是否有暗樁）
        """
        occupations = ["資深硬體工程師", "精打細算的會計", "務實的家庭主婦", "電子產品評測員", "傳統工匠", "軟體開發者"]
        
        if has_plants:
            # 實驗組：3位暗樁 + 3位理性消費者
            for i in range(3):
                plant = FocusGroupFactory.create_plant_agent(f"Participant_Plant_{i+1}", self.group_name)
                self.participants.append(plant)
                self.world.add_agent(plant)
                
            for i in range(3, 6):
                subject = FocusGroupFactory.create_rational_subject(f"Participant_Subject_{i+1}", self.group_name, occupations[i])
                self.participants.append(subject)
                self.world.add_agent(subject)
        else:
            # 對照組：6位全都是理性消費者
            for i in range(6):
                subject = FocusGroupFactory.create_rational_subject(f"Participant_Subject_{i+1}", self.group_name, occupations[i])
                self.participants.append(subject)
                self.world.add_agent(subject)

        self.world.make_everyone_accessible()

    def run_experiment(self, total_rounds: int):
        print(f"\n===== [{self.group_name}] 焦點小組盲測會啟動 =====")
        
        # 第一輪：主持人介紹產品並要求分享初步感受
        self.world.broadcast(
            f"【主持人廣播】歡迎各位來到新品盲測會。請大家戴上發給你們的產品：\n"
            f"產品介紹：{self.product_description}\n"
            "現在，請各位仔細感受它，並輪流分享你們的『初次體驗與感覺』。這東西到底神奇在哪裡？"
        )
        self.world.run(1)

        # 中間輪次：自由討論，暗樁開始帶風向
        if total_rounds > 2:
            for r in range(2, total_rounds):
                self.world.broadcast(f"【主持人廣播】討論進入第 {r} 輪。請大家針對剛才其他人的發言，說說你們的看法。你們有沒有感覺到別人說的那種奇妙體驗？")
                self.world.run(1)

        # 最後一輪：強制決策 (購買意願)
        self.world.broadcast(
            "【主持人廣播】盲測會即將結束。這款『空靈智慧環』的早鳥定價是 299 美金。\n"
            "請各位在發言的最後，明確寫出：1. 你的最終評價（你會怎麼形容這個產品） 2. 你是否願意購買（『願意購買』或『拒絕購買』）。"
        )
        self.world.run(1)
        
        print(f"===== [{self.group_name}] 焦點小組盲測會結束 =====\n")