"""
技能基礎模組
定義技能的抽象基類與通用介面
所有具體技能必須繼承此基類並實作抽象方法
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from models import AgentState


class BaseSkill(ABC):
    """
    技能抽象基類
    定義技能的基本屬性與執行介面
    """

    def __init__(self, skill_id: str, name: str):
        """
        初始化技能
        參數:
            skill_id: 技能唯一識別碼
            name: 技能名稱
        """
        self.skill_id = skill_id
        self.name = name

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """
        執行技能（抽象方法）
        參數:
            state: 當前 Agent 狀態
        回傳:
            執行後的 Agent 狀態
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """
        驗證技能有效性（抽象方法）
        回傳:
            布林值表示技能是否有效
        """
        pass
