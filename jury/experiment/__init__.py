"""
jury/experiment 子套件 — 各階段實驗的執行入口。

子模組：
  models             — VotingRecord、VotingStats、verdict 常數
  parser             — ResponseParser（Agent 回應解析）
  voter              — OccupationCategoryMapper、build_persona_id、PersonaVoter
  stats              — StatsCalculator（統計摘要計算）
  baseline           — BaselineResultsWriter（持久化 dominant_verdict）
  individual_voting  — PersonaLoader、IndividualVotingRunner、CLI（Phase 2 執行入口）
"""
