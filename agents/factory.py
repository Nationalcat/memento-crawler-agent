"""
工廠模式模組
實作 Agent 的建立與管理機制
透過工廠模式實現不同類型 Agent 的統一建立介面
使用單例模式確保全域只有一個工廠實例
"""
from abc import ABC, abstractmethod
from typing import Dict, Type, Optional
from enum import Enum
from models import AgentState


class AgentType(str, Enum):
    """
    Agent 類型列舉
    定義系統中可用的 Agent 類型
    """
    HARNESS = "harness"      # Harness 控制層：負責任務解析、技能選擇、流程控制
    EXECUTOR = "executor"    # 執行層：負責實際的網頁互動與資料抓取
    ANALYZER = "analyzer"    # 分析層：負責資料清洗與結構化分析


class BaseAgent(ABC):
    """
    Agent 抽象基類
    定義所有 Agent 必須實作的方法介面
    """

    def __init__(self, agent_id: str, agent_type: AgentType):
        """
        初始化 Agent
        參數:
            agent_id: Agent 唯一識別碼
            agent_type: Agent 類型
        """
        self.agent_id = agent_id
        self.agent_type = agent_type

    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        """
        處理 Agent 狀態（抽象方法）
        參數:
            state: 當前 Agent 狀態
        回傳:
            處理後的 Agent 狀態
        """
        pass


class AgentFactory:
    """
    Agent 工廠（單例模式）
    負責建立與管理不同類型的 Agent 實例
    使用單例模式確保全域只有一個工廠，統一管理 Agent 的建立
    """
    _instance: Optional['AgentFactory'] = None              # 單例實例
    _registry: Dict[AgentType, Type[BaseAgent]] = {}        # Agent 類型註冊表

    def __new__(cls):
        """單例模式實作：確保只建立一個工廠實例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, agent_type: AgentType, agent_class: Type[BaseAgent]) -> None:
        """
        註冊 Agent 類別到工廠
        參數:
            agent_type: Agent 類型列舉值
            agent_class: Agent 類別（必須繼承 BaseAgent）
        """
        cls._registry[agent_type] = agent_class

    @classmethod
    def create(cls, agent_type: AgentType, agent_id: str) -> BaseAgent:
        """
        建立 Agent 實例
        參數:
            agent_type: 要建立的 Agent 類型
            agent_id: Agent 唯一識別碼
        回傳:
            Agent 實例
        例外:
            ValueError: 若未註冊該 Agent 類型
        """
        if agent_type not in cls._registry:
            raise ValueError(f"未知的 Agent 類型: {agent_type}")
        return cls._registry[agent_type](agent_id, agent_type)

    @classmethod
    def reset(cls) -> None:
        """重置工廠（用於測試）"""
        cls._instance = None
        cls._registry = {}
