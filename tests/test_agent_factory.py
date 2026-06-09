import pytest
from agents.factory import AgentFactory, AgentType, BaseAgent
from models import AgentState

class MockAgent(BaseAgent):
    """測試用的 Mock Agent"""
    async def process(self, state: AgentState) -> AgentState:
        state["metadata"]["processed_by"] = self.agent_id
        return state

@pytest.fixture(autouse=True)
def clean_factory():
    """每個測試執行前/後，重置 AgentFactory 的狀態"""
    AgentFactory.reset()
    yield
    AgentFactory.reset()

def test_singleton_pattern():
    """測試 AgentFactory 是否為單例模式"""
    factory1 = AgentFactory()
    factory2 = AgentFactory()
    assert factory1 is factory2

def test_agent_registration_and_creation():
    """測試註冊與建立 Agent 實例"""
    # 註冊 MockAgent 為 HARNESS 類型
    AgentFactory.register(AgentType.HARNESS, MockAgent)
    
    # 驗證註冊表已包含此類型
    assert AgentType.HARNESS in AgentFactory._registry
    assert AgentFactory._registry[AgentType.HARNESS] is MockAgent

    # 建立實例
    agent = AgentFactory.create(AgentType.HARNESS, "test-harness-1")
    assert isinstance(agent, MockAgent)
    assert agent.agent_id == "test-harness-1"
    assert agent.agent_type == AgentType.HARNESS

def test_unregistered_agent_type_raises_error():
    """測試建立未註冊的 Agent 類型時會拋出 ValueError"""
    with pytest.raises(ValueError) as excinfo:
        AgentFactory.create(AgentType.EXECUTOR, "test-executor-1")
    
    assert "未知的 Agent 類型: AgentType.EXECUTOR" in str(excinfo.value)

@pytest.mark.asyncio
async def test_agent_process_behavior():
    """測試建立出來的 Agent 能夠正常執行 process 邏輯"""
    AgentFactory.register(AgentType.ANALYZER, MockAgent)
    agent = AgentFactory.create(AgentType.ANALYZER, "test-analyzer-1")
    
    dummy_state = {
        "task_id": "t1",
        "metadata": {}
    }
    
    # 呼叫 process
    result = await agent.process(dummy_state)
    assert result["metadata"]["processed_by"] == "test-analyzer-1"

def test_reset_factory():
    """測試重置工廠狀態"""
    AgentFactory.register(AgentType.HARNESS, MockAgent)
    assert len(AgentFactory._registry) == 1
    
    AgentFactory.reset()
    assert len(AgentFactory._registry) == 0
    assert AgentFactory._instance is None

@pytest.mark.asyncio
async def test_base_agent_abc_methods():
    """測試 BaseAgent 抽象基類的 process 方法的 pass，以達到 100% 覆蓋率"""
    class TestAgent(BaseAgent):
        async def process(self, state):
            return await super().process(state)
            
    ta = TestAgent("test-id", AgentType.HARNESS)
    assert await ta.process({"task_id": "test"}) is None
