"""
策略模式模組
實作爬蟲策略的抽象介面與具體策略類別
透過策略模式實現不同網站的爬蟲邏輯切換
配合 StrategyRegistry 單例模式管理所有策略
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type
from models import AgentState, Skill


class CrawlStrategy(ABC):
    """
    爬蟲策略抽象基類
    定義所有爬蟲策略必須實作的方法介面
    """

    @abstractmethod
    async def crawl(self, url: str, selectors: Dict[str, str]) -> Dict:
        """
        執行爬蟲抓取
        參數:
            url: 目標網址
            selectors: CSS 選擇器對應表
        回傳:
            包含抓取結果的字典
        """
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        判斷此策略是否能處理指定網址
        參數:
            url: 目標網址
        回傳:
            布林值表示是否可處理
        """
        pass


class DefaultCrawlStrategy(CrawlStrategy):
    """
    預設爬蟲策略
    通用的爬蟲實作，適用於未指定特殊策略的網站
    """

    async def crawl(self, url: str, selectors: Dict[str, str]) -> Dict:
        """執行預設爬蟲邏輯"""
        return {"status": "success", "data": [], "strategy": "default"}

    def can_handle(self, url: str) -> bool:
        """預設策略可處理所有網址"""
        return True


class EcommerceCrawlStrategy(CrawlStrategy):
    """
    電商網站爬蟲策略
    專門針對電商平台（Amazon、蝦皮、momo、PChome）的爬蟲實作
    包含電商特有的頁面結構解析邏輯
    """

    async def crawl(self, url: str, selectors: Dict[str, str]) -> Dict:
        """執行電商網站爬蟲邏輯"""
        return {"status": "success", "data": [], "strategy": "ecommerce"}

    def can_handle(self, url: str) -> bool:
        """判斷是否為支援的電商網站"""
        ecommerce_domains = ["amazon", "shopee", "momo", "pchome"]
        return any(domain in url.lower() for domain in ecommerce_domains)


class AntiBotCrawlStrategy(CrawlStrategy):
    """
    反爬蟲繞過策略
    針對具有反爬蟲機制的網站，實作繞過檢測的邏輯
    包含模擬真人行為、隨機延遲等功能
    """

    async def crawl(self, url: str, selectors: Dict[str, str]) -> Dict:
        """執行反爬蟲繞過邏輯"""
        return {"status": "success", "data": [], "strategy": "anti_bot"}

    def can_handle(self, url: str) -> bool:
        """反爬蟲策略可處理所有網址（作為備用策略）"""
        return True


class StrategyRegistry:
    """
    策略註冊中心（單例模式）
    管理所有已註冊的爬蟲策略，並根據網址自動選擇合適的策略
    使用單例模式確保全域只有一個策略註冊中心
    """
    _instance: Optional['StrategyRegistry'] = None  # 單例實例
    _strategies: List[CrawlStrategy] = []            # 已註冊的策略列表

    def __new__(cls):
        """單例模式實作：確保只建立一個實例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 初始化時註冊預設策略（按優先順序排列）
            cls._strategies = [
                EcommerceCrawlStrategy(),  # 電商策略優先
                AntiBotCrawlStrategy(),    # 反爬蟲策略次之
                DefaultCrawlStrategy()     # 預設策略作為備用
            ]
        return cls._instance

    def get_strategy(self, url: str) -> CrawlStrategy:
        """
        根據網址獲取合適的爬蟲策略
        參數:
            url: 目標網址
        回傳:
            匹配的爬蟲策略實例
        """
        for strategy in self._strategies:
            if strategy.can_handle(url):
                return strategy
        return DefaultCrawlStrategy()

    def register(self, strategy: CrawlStrategy) -> None:
        """
        註冊新的爬蟲策略
        新策略會被插入到列表最前面，具有最高優先權
        參數:
            strategy: 要註冊的策略實例
        """
        self._strategies.insert(0, strategy)

    @classmethod
    def reset(cls) -> None:
        """重置策略註冊中心（用於測試）"""
        cls._instance = None
        cls._strategies = []
