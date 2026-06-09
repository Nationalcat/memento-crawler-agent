import pytest
from skills.strategy import (
    StrategyRegistry,
    CrawlStrategy,
    DefaultCrawlStrategy,
    EcommerceCrawlStrategy,
    AntiBotCrawlStrategy
)

@pytest.fixture(autouse=True)
def clean_registry():
    """每個測試執行前/後，重置 StrategyRegistry 的狀態"""
    StrategyRegistry.reset()
    yield
    StrategyRegistry.reset()

def test_singleton_pattern():
    """測試 StrategyRegistry 是否為單例模式"""
    registry1 = StrategyRegistry()
    registry2 = StrategyRegistry()
    assert registry1 is registry2

def test_default_strategies_registered():
    """測試 StrategyRegistry 初始化時是否自動註冊了預設策略"""
    registry = StrategyRegistry()
    # 預設註冊了 EcommerceCrawlStrategy, AntiBotCrawlStrategy, DefaultCrawlStrategy
    # 依照優先順序，Ecommerce 最前，Default 最後
    assert len(registry._strategies) == 3
    assert isinstance(registry._strategies[0], EcommerceCrawlStrategy)
    assert isinstance(registry._strategies[1], AntiBotCrawlStrategy)
    assert isinstance(registry._strategies[2], DefaultCrawlStrategy)

@pytest.mark.parametrize("url,expected_strategy_class", [
    ("https://shopee.tw/product/123", EcommerceCrawlStrategy),
    ("https://www.amazon.com/dp/B000000", EcommerceCrawlStrategy),
    ("https://momo.com.tw/goods", EcommerceCrawlStrategy),
    ("https://pchome.com.tw/prod", EcommerceCrawlStrategy),
    ("https://example.com/blog", AntiBotCrawlStrategy), # 預設非電商網站，因為 AntiBot 也能 handle 且優先於 Default
    ("https://test.org", AntiBotCrawlStrategy)
])
def test_strategy_matching(url, expected_strategy_class):
    """測試根據不同網址是否選擇了正確的爬蟲策略"""
    registry = StrategyRegistry()
    strategy = registry.get_strategy(url)
    assert isinstance(strategy, expected_strategy_class)

@pytest.mark.asyncio
async def test_custom_strategy_registration():
    """測試自定義策略註冊且優先級最高"""
    class CustomCrawlStrategy(CrawlStrategy):
        async def crawl(self, url, selectors):
            return {"status": "success", "strategy": "custom"}
        
        def can_handle(self, url):
            return "custom-domain.com" in url

    registry = StrategyRegistry()
    custom_strategy = CustomCrawlStrategy()
    
    # 註冊新策略
    registry.register(custom_strategy)
    
    # 檢查是否插入到最前面（最高優先級）
    assert registry._strategies[0] is custom_strategy
    
    # 測試是否能成功匹配該網址
    resolved_strategy = registry.get_strategy("https://custom-domain.com/page")
    assert resolved_strategy is custom_strategy
    res = await resolved_strategy.crawl("https://custom-domain.com/page", {})
    assert res == {"status": "success", "strategy": "custom"}

@pytest.mark.asyncio
async def test_strategy_crawl_behavior():
    """測試各策略的 crawl 方法回傳值格式"""
    default_strategy = DefaultCrawlStrategy()
    res1 = await default_strategy.crawl("http://example.com", {})
    assert res1 == {"status": "success", "data": [], "strategy": "default"}
    assert default_strategy.can_handle("http://example.com") is True

    ecommerce_strategy = EcommerceCrawlStrategy()
    res2 = await ecommerce_strategy.crawl("https://amazon.com", {})
    assert res2 == {"status": "success", "data": [], "strategy": "ecommerce"}
    assert ecommerce_strategy.can_handle("https://amazon.com") is True
    assert ecommerce_strategy.can_handle("https://example.com") is False

    antibot_strategy = AntiBotCrawlStrategy()
    res3 = await antibot_strategy.crawl("https://example.com", {})
    assert res3 == {"status": "success", "data": [], "strategy": "anti_bot"}
    assert antibot_strategy.can_handle("https://example.com") is True

def test_registry_fallback_when_empty():
    """測試當註冊中心為空（無匹配策略）時，回傳 DefaultCrawlStrategy"""
    registry = StrategyRegistry()
    registry._strategies = [] # 手動清空
    strategy = registry.get_strategy("https://any-url.com")
    assert isinstance(strategy, DefaultCrawlStrategy)

@pytest.mark.asyncio
async def test_crawl_strategy_abc_methods():
    """測試 CrawlStrategy 抽象基類的 pass 行以實現 100% 覆蓋率"""
    class TestStrategy(CrawlStrategy):
        async def crawl(self, url, selectors):
            return await super().crawl(url, selectors)
        def can_handle(self, url):
            return super().can_handle(url)
            
    ts = TestStrategy()
    # 呼叫 super() 方法會執行到基類的 pass
    await ts.crawl("http://test", {})
    ts.can_handle("http://test")
