import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from models import TaskStatus, AgentState
from skills.models import CommunitySkill, TargetConfig, CrawlAction
from agents.factory import AgentType, AgentFactory
from agents.executor import ExecutorAgent

# Helper to create a blank template AgentState
def create_executor_state(task_id="t1", url="example.com", source="skill", skill_obj=None) -> AgentState:
    return {
        "task_id": task_id,
        "url": url,
        "instruction": "extract pricing",
        "status": TaskStatus.PENDING,
        "current_step": 0,
        "total_steps": 10,
        "extracted_data": [],
        "error_log": [],
        "skill_id": None,
        "use_skill": False,
        "skill_failed": False,
        "execution_source": source,
        "skill_object": skill_obj,
        "retry_count": 0,
        "start_time": datetime.now(),
        "end_time": None,
        "metadata": {},
        "current_strategy": None,
        "original_strategy": None,
        "reject_reason": None
    }

@pytest.fixture
def mock_executor_dependencies():
    """Mock out BrowserManager, CommunitySkillExecutor, prompt_loader, llm_manager, and generate_skill"""
    with patch("agents.executor.BrowserManager") as MockBrowserManager, \
         patch("agents.executor.CommunitySkillExecutor") as MockCommunitySkillExecutor, \
         patch("agents.executor.prompt_loader") as mock_prompt_loader, \
         patch("agents.executor.generate_skill_from_execution") as mock_gen_skill, \
         patch("agents.executor.SkillMemory") as MockSkillMemory:
         
         # Setup mock browser
         mock_browser = MagicMock()
         mock_browser.initialize = AsyncMock()
         html_content = """
         <html>
           <h1>模擬_title_資料</h1>
           <p>模擬_content_資料</p>
           <div class="price">模擬_price_資料</div>
         </html>
         """
         mock_browser.navigate = AsyncMock(return_value=html_content)
         mock_browser.get_content = AsyncMock(return_value=html_content)
         mock_browser.click = AsyncMock(return_value=True)
         mock_browser.scroll = AsyncMock()
         mock_browser.close = AsyncMock()
         mock_browser.wait = AsyncMock()
         mock_browser.wait_for_element = AsyncMock()
         mock_browser.input = AsyncMock()
         MockBrowserManager.return_value = mock_browser

         # Setup mock community executor
         mock_comm_exec = MagicMock()
         mock_comm_exec.extract_data.return_value = [{"price": "100"}]
         MockCommunitySkillExecutor.return_value = mock_comm_exec
         
         # Setup mock memory
         mock_mem = MagicMock()
         MockSkillMemory.return_value = mock_mem
         
         yield {
             "browser": mock_browser,
             "comm_exec": mock_comm_exec,
             "prompt_loader": mock_prompt_loader,
             "gen_skill": mock_gen_skill,
             "memory": mock_mem
         }

def test_executor_init(mock_executor_dependencies):
    """測試 ExecutorAgent 的初始化與在工廠中的註冊"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    assert agent.agent_id == "exec-1"
    assert agent.agent_type == AgentType.EXECUTOR
    assert agent.browser is mock_executor_dependencies["browser"]
    # 驗證是否在工廠中註冊（確保在其他測試重置後重新註冊）
    if AgentType.EXECUTOR not in AgentFactory._registry:
        AgentFactory.register(AgentType.EXECUTOR, ExecutorAgent)
    assert AgentFactory._registry[AgentType.EXECUTOR] is ExecutorAgent

@pytest.mark.asyncio
async def test_process_dispatch(mock_executor_dependencies):
    """測試 process 流程的分流"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    
    # Mock execute_with_skill 與 execute_auto
    agent.execute_with_skill = AsyncMock(return_value="skill_run")
    agent.execute_auto = AsyncMock(return_value="auto_run")
    
    # 1. 走向 execute_with_skill
    state_skill = create_executor_state(source="skill", skill_obj={"id": "skill_a"})
    res_skill = await agent.process(state_skill)
    assert res_skill == "skill_run"
    agent.execute_with_skill.assert_called_once_with(state_skill)
    
    # 2. 走向 execute_auto
    state_auto = create_executor_state(source="auto")
    res_auto = await agent.process(state_auto)
    assert res_auto == "auto_run"
    agent.execute_auto.assert_called_once_with(state_auto)

@pytest.mark.asyncio
async def test_execute_with_skill_community(mock_executor_dependencies):
    """測試使用 CommunitySkill 執行爬取"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    
    # 建立含 actions 的 CommunitySkill
    actions = [
        CrawlAction(type="wait", timeout=500),
        CrawlAction(type="wait"), # 沒有 timeout 以測試 fallback
        CrawlAction(type="scroll", times=2),
        CrawlAction(type="scroll"), # 沒有 times 以測試 fallback
        CrawlAction(type="click", selector=".btn"),
        CrawlAction(type="wait_for", selector=".loaded", timeout=2000),
        CrawlAction(type="wait_for", selector=".loaded"), # 沒有 timeout 測試 fallback
        CrawlAction(type="input", selector=".input", value="hello"),
        CrawlAction(type="input", selector=".input") # 沒有 value 測試 fallback
    ]
    skill = CommunitySkill(
        id="yaml-skill",
        name="Yaml Scraper",
        target=TargetConfig(domain="example.com"),
        execution={"actions": actions}
    )
    
    state = create_executor_state(source="skill", skill_obj=skill)
    res = await agent.execute_with_skill(state)
    
    assert res["status"] == TaskStatus.COMPLETED
    assert res["extracted_data"] == [{"price": "100"}]
    
    # 驗證動作是否正確被呼叫
    mock_executor_dependencies["browser"].wait.assert_any_call(500)
    mock_executor_dependencies["browser"].wait.assert_any_call(1000)
    assert mock_executor_dependencies["browser"].scroll.call_count == 3 # times=2 + times=1
    mock_executor_dependencies["browser"].click.assert_called_with(".btn")
    mock_executor_dependencies["browser"].wait_for_element.assert_any_call(".loaded", 2000)
    mock_executor_dependencies["browser"].wait_for_element.assert_any_call(".loaded", 10000)
    mock_executor_dependencies["browser"].input.assert_any_call(".input", "hello")
    mock_executor_dependencies["browser"].input.assert_any_call(".input", "")
    mock_executor_dependencies["browser"].close.assert_called_once()

@pytest.mark.asyncio
async def test_execute_with_skill_auto_json(mock_executor_dependencies):
    """測試使用自動生成的 JSON 技能字典執行"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    skill_dict = {
        "id": "json-skill",
        "selectors": {"selector_based": "h1"}
    }
    
    state = create_executor_state(source="skill", skill_obj=skill_dict)
    res = await agent.execute_with_skill(state)
    
    assert res["status"] == TaskStatus.COMPLETED
    # 驗證 _extract_with_selectors 的模擬回傳
    assert len(res["extracted_data"]) == 1
    assert "selector_based" in res["extracted_data"][0]

@pytest.mark.asyncio
async def test_execute_with_skill_invalid_type(mock_executor_dependencies):
    """測試傳入不支援的技能物件類型以驗證異常捕捉"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    
    state = create_executor_state(source="skill", skill_obj=12345) # 壞的類型
    res = await agent.execute_with_skill(state)
    
    assert res["status"] == TaskStatus.FAILED
    assert any("[Skill執行錯誤]" in err for err in res["error_log"])

@pytest.mark.asyncio
async def test_execute_auto_success_llm(mock_executor_dependencies):
    """測試 execute_auto 自動執行 (LLM 調用成功)"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    mock_executor_dependencies["prompt_loader"].get_prompt.return_value = "prompt"
    
    with patch("utils.llm_manager.analyze_webpage", new_callable=AsyncMock) as mock_llm:
        # 1. 模擬策略返回 (缺 fields 與 actions)
        mock_llm.return_value = {}
        
        state = create_executor_state(source="auto")
        res = await agent.execute_auto(state)
        
        assert res["status"] == TaskStatus.COMPLETED
        assert res["current_strategy"]["fields"] == []
        assert res["current_strategy"]["actions"] == ["scroll"]
        assert res["extracted_data"] == [] # 提取空 dict
        
        # 2. 模擬策略返回 (完整 fields 與 actions)
        mock_llm.return_value = {
            "fields": [{"name": "price", "selector": ".price"}],
            "actions": ["wait"]
        }
        state2 = create_executor_state(source="auto")
        res2 = await agent.execute_auto(state2)
        assert res2["status"] == TaskStatus.COMPLETED
        assert res2["extracted_data"] == [{"price": "模擬_price_資料"}]

@pytest.mark.asyncio
async def test_execute_auto_llm_exception(mock_executor_dependencies):
    """測試 execute_auto 自動執行 (LLM 發生異常，使用預設策略)"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    mock_executor_dependencies["prompt_loader"].get_prompt.return_value = "prompt"
    
    with patch("utils.llm_manager.analyze_webpage", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = RuntimeError("API key invalid")
        
        state = create_executor_state(source="auto")
        res = await agent.execute_auto(state)
        
        assert res["status"] == TaskStatus.COMPLETED
        assert "API key invalid" in res["current_strategy"]["llm_error"]
        assert res["current_strategy"]["fields"][0]["name"] == "title"
        assert res["extracted_data"] == [{"title": "模擬_title_資料", "content": "模擬_content_資料"}]

@pytest.mark.asyncio
async def test_execute_auto_overall_exception(mock_executor_dependencies):
    """測試 execute_auto 因瀏覽器崩潰或導航失敗等引發的整體異常"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    # 模擬瀏覽器 navigate 拋出 Exception
    mock_executor_dependencies["browser"].navigate.side_effect = RuntimeError("Crash")
    
    state = create_executor_state(source="auto")
    res = await agent.execute_auto(state)
    
    assert res["status"] == TaskStatus.FAILED
    assert any("[自動執行錯誤] Crash" in err for err in res["error_log"])
    mock_executor_dependencies["browser"].close.assert_called_once()

@pytest.mark.asyncio
async def test_save_skill_from_execution(mock_executor_dependencies):
    """測試 save_skill_from_execution"""
    agent = ExecutorAgent("exec-1", AgentType.EXECUTOR)
    
    # 1. 任務未 COMPLETED 時呼叫，應直接返回 (無動作)
    state_pending = create_executor_state(source="auto")
    state_pending["status"] = TaskStatus.FAILED
    await agent.save_skill_from_execution(state_pending)
    mock_executor_dependencies["gen_skill"].assert_not_called()

    # 2. 任務已 COMPLETED 時，應正常調用生成與儲存
    mock_skill = CommunitySkill(id="new-skill-1", name="name", target=TargetConfig(domain="e.com"))
    mock_executor_dependencies["gen_skill"].return_value = mock_skill
    
    state_comp = create_executor_state(source="auto")
    state_comp["status"] = TaskStatus.COMPLETED
    state_comp["current_strategy"] = {
        "fields": [{"name": "price"}],
        "execution": {"wait": 3},
        "prompt": "prompt string"
    }
    
    await agent.save_skill_from_execution(state_comp)
    
    assert state_comp["skill_id"] == "new-skill-1"
    assert state_comp["metadata"]["skill_action"] == "created"
    mock_executor_dependencies["gen_skill"].assert_called_once()
    mock_executor_dependencies["memory"].store_community_skill.assert_called_with(mock_skill)
