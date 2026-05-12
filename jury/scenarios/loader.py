"""
Scenario YAML 載入器。

職責：
  1. 從指定 YAML 路徑讀取所有 Scenario
  2. 對每筆 Scenario 執行 ScenarioValidator 驗證
  3. 提供依 scenario_id 查詢的介面

YAML 結構約定（見 jury/config/scenarios.yaml）：
  scenarios:
    - scenario_id: ...
      ...
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from .models import Scenario
from .validator import ScenarioValidator, ScenarioValidationError

# 預設 YAML 路徑（相對於本檔案的位置往上兩層再進 config/）
_DEFAULT_YAML_PATH = Path(__file__).parent.parent / "config" / "scenarios.yaml"


class ScenarioNotFoundError(KeyError):
    """以 scenario_id 查詢時找不到對應 Scenario 時拋出。"""

    def __init__(self, scenario_id: str) -> None:
        super().__init__(f"Scenario '{scenario_id}' not found in loaded scenarios.")


class ScenarioLoader:
    """
    從 YAML 檔案載入並驗證 Scenario 列表。

    使用方式：
        loader = ScenarioLoader()                          # 使用預設路徑
        loader = ScenarioLoader(path=Path("custom.yaml")) # 自訂路徑
        scenarios = loader.load_all()
        scenario  = loader.load_by_id("father_theft_medicine")
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        validator: Optional[ScenarioValidator] = None,
    ) -> None:
        # 允許外部注入路徑與驗證器，方便測試與擴充
        self._path = path or _DEFAULT_YAML_PATH
        self._validator = validator or ScenarioValidator()
        self._cache: Optional[list[Scenario]] = None  # 避免重複讀取磁碟

    def load_all(self, *, validate: bool = True) -> list[Scenario]:
        """
        載入 YAML 中所有 Scenario。

        Parameters
        ----------
        validate : bool
            若為 True（預設），每筆 Scenario 均執行嚴格驗證；
            驗證失敗時拋出 ScenarioValidationError。
        """
        if self._cache is not None:
            return self._cache

        if not self._path.exists():
            raise FileNotFoundError(
                f"Scenarios YAML not found at: {self._path}. "
                "Please create jury/config/scenarios.yaml."
            )

        with self._path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        raw_scenarios = raw.get("scenarios", [])
        if not raw_scenarios:
            raise ValueError(
                f"No scenarios found in '{self._path}'. "
                "YAML must have a top-level 'scenarios' list."
            )

        scenarios: list[Scenario] = []
        for item in raw_scenarios:
            scenario = Scenario.from_dict(item)
            if validate:
                # 嚴格驗證，任一欄位缺失均拋出例外
                self._validator.validate(scenario)
            scenarios.append(scenario)

        self._cache = scenarios
        return scenarios

    def load_by_id(self, scenario_id: str) -> Scenario:
        """
        依 scenario_id 查詢並回傳單一 Scenario。

        Raises
        ------
        ScenarioNotFoundError
            找不到對應 scenario_id 時拋出。
        """
        all_scenarios = self.load_all()
        for scenario in all_scenarios:
            if scenario.scenario_id == scenario_id:
                return scenario
        raise ScenarioNotFoundError(scenario_id)

    def invalidate_cache(self) -> None:
        """清除快取，下次 load_all() 將重新讀取磁碟。"""
        self._cache = None
