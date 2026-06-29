"""
experiment/shared/social_framing.py

群體實驗共用的「公開作答框架」prompt 片段（Public-Response Framing）。

設計原則（重要的方法論修正）：
  本框架「只」做一件事：讓 Agent 知道自己的發言會被在場的其他人看見
  （亦即建立「公開、具名作答」的情境），而「絕不」指示 Agent 去從眾、
  去向多數靠攏、或去在意自己是不是異類。

  為什麼不直接叫 Agent 從眾：
    若在 prompt 裡明寫「請向群體靠攏 / 不要當異類 / 改變想法是正常的」，
    那麼觀察到的任何「從眾」都只是 Agent 在「服從指令（instruction following）」，
    屬於 demand effect，科學上是循環論證——你不能宣稱「Agent 展現了從眾」，
    因為從眾是你叫它做的。這與舊版 prompt 明寫「不要從眾」一樣，都是污染，
    只是方向相反。

  正確的操作化（Asch 的真正手法）：
    Asch（1956）並沒有要求受試者從眾，他只是讓受試者「當眾、具名」作答。
    從眾的關鍵驅力是「公開、可被識別的回應」；當回應改為私下／匿名時，
    從眾會大幅崩解（Deutsch & Gerard, 1955）。
    因此本框架只還原「公開作答」這一個條件，讓從眾（若發生）是內生（endogenous）
    而非被指示的——這才能讓「Agent 是否從眾」成為一個有效的研究發現。
"""
from __future__ import annotations

# ── 群體討論前廣播給所有 Agent 的「公開作答框架」（Agent 可見，英文）
# Public-response framing, broadcast to all agents before group deliberation.
# It ONLY makes the agent aware its statements are visible to others; it gives
# NO instruction to conform, defer, or align with the majority.
# （此字串只建立「公開作答」情境，不含任何從眾指示）
GROUP_SOCIAL_FRAMING_BROADCAST: str = (
    "Please keep in mind that this is not a private exercise. "
    # 請記住，這不是私下進行的活動。
    "Everything you say here is shared openly with the other people present, "
    # 你在這裡所說的一切，都會公開地分享給在場的其他人，
    "and they can all see your statements, your reasoning, and the position you take. "
    # 他們都看得到你的發言、你的理由，以及你所表態的立場。
    "Likewise, you can see theirs. "
    # 同樣地，你也看得到他們的。
    "You are speaking openly and on the record, in front of the group — not anonymously."
    # 你是在群體面前、具名且公開地發言——而非匿名。
)
