import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from models import TaskStatus, AgentState
from agents.factory import AgentType, AgentFactory
from skills.models import CommunitySkill, TargetConfig
from agents.harness import Harness

# Helper to create a blank template AgentState
def create_blank_state(task_id="t1", url="example.com", instruction="grab price") -> AgentState:
    return {
        "task_id": task_id,
        "url": url,
        "instruction": instruction,
        "status": TaskStatus.PENDING,
        "current_step": 0,
        "total_steps": 10,
        "extracted_data": [],
        "error_log": [],
        "skill_id": None,
        "use_skill": False,
        "skill_failed": False,
        "execution_source": "none",
        "skill_object": None,
        "retry_count": 0,
        "start_time": datetime.now(),
        "end_time": None,
        "metadata": {},
        "current_strategy": None,
        "original_strategy": None,
        "reject_reason": None
    }

@pytest.fixture
def mock_dependencies():
    """使用 patch 模擬外部模組/依賴"""
    with patch("agents.harness.SkillMemory") as MockSkillMemory, \
         patch("agents.harness.BrowserManager") as MockBrowserManager, \
         patch("agents.harness.generate_skill_from_execution") as mock_gen_skill:
        
        # 建立模擬實例
        mock_mem = MagicMock()
        MockSkillMemory.return_value = mock_mem
        
        yield {
            "memory": mock_mem,
            "browser": MockBrowserManager,
            "gen_skill": mock_gen_skill
        }

def test_harness_init(mock_dependencies):
    """測試 Harness 的初始化與自動註冊"""
    harness = Harness("h-1", AgentType.HARNESS)
    assert harness.agent_id == "h-1"
    assert harness.agent_type == AgentType.HARNESS
    assert harness.skill_memory is mock_dependencies["memory"]
    
    # 驗證是否在工廠中註冊（確保在其他測試重置後重新註冊）
    if AgentType.HARNESS not in AgentFactory._registry:
        AgentFactory.register(AgentType.HARNESS, Harness)
    assert AgentFactory._registry[AgentType.HARNESS] is Harness

@pytest.mark.asyncio
async def test_harness_process(mock_dependencies):
    """測試 Harness.process"""
    harness = Harness("h-1", AgentType.HARNESS)
    state = create_blank_state()
    res = await harness.process(state)
    assert res["status"] == TaskStatus.PARSING

@pytest.mark.asyncio
async def test_validate_input_valid(mock_dependencies):
    """測試 validate_input（合法的輸入）"""
    harness = Harness("h-1", AgentType.HARNESS)
    mock_dependencies["browser"].normalize_url.return_value = "https://example.com"
    
    state = create_blank_state()
    res = await harness.validate_input(state)
    
    assert res["status"] == TaskStatus.PARSING
    assert res["url"] == "https://example.com"
    assert res["use_skill"] is False
    assert res["reject_reason"] is None
    mock_dependencies["browser"].normalize_url.assert_called_with("example.com")

@pytest.mark.asyncio
async def test_validate_input_url_empty(mock_dependencies):
    """測試 validate_input（網址為空，任務被拒絕）"""
    harness = Harness("h-1", AgentType.HARNESS)
    state = create_blank_state(url="")
    res = await harness.validate_input(state)
    
    assert res["status"] == TaskStatus.REJECTED
    assert res["reject_reason"] == "url_empty"
    assert "請提供有效的網址" in res["error_log"]

@pytest.mark.asyncio
async def test_validate_input_instruction_empty(mock_dependencies):
    """測試 validate_input（指令為空，任務被拒絕）"""
    harness = Harness("h-1", AgentType.HARNESS)
    state = create_blank_state(instruction="")
    res = await harness.validate_input(state)
    
    assert res["status"] == TaskStatus.REJECTED
    assert res["reject_reason"] == "instruction_empty"
    assert "請提供爬取指令" in res["error_log"]

@pytest.mark.asyncio
async def test_check_url_access_success(mock_dependencies):
    """測試 check_url_access（訪問成功）"""
    harness = Harness("h-1", AgentType.HARNESS)
    mock_dependencies["browser"].check_url_status = AsyncMock(return_value={"accessible": True, "status_code": 200, "message": "正常"})
    
    state = create_blank_state(url="https://accessible.com")
    res = await harness.check_url_access(state)
    
    assert res["status"] == TaskStatus.PARSING
    assert res["reject_reason"] is None

@pytest.mark.asyncio
async def test_check_url_access_failure(mock_dependencies):
    """測試 check_url_access（訪問失敗，任務被拒絕）"""
    harness = Harness("h-1", AgentType.HARNESS)
    mock_dependencies["browser"].check_url_status = AsyncMock(return_value={"accessible": False, "status_code": 404, "message": "頁面不存在"})
    
    state = create_blank_state(url="https://inaccessible.com")
    res = await harness.check_url_access(state)
    
    assert res["status"] == TaskStatus.REJECTED
    assert res["reject_reason"] == "url_inaccessible"
    assert "頁面不存在" in res["error_log"]
    assert res["metadata"]["status_code"] == 404

@pytest.mark.asyncio
async def test_retrieve_skill_none(mock_dependencies):
    """測試 retrieve_skill（沒有找到技能）"""
    harness = Harness("h-1", AgentType.HARNESS)
    mock_dependencies["memory"].retrieve_skill.return_value = None
    
    state = create_blank_state()
    res = await harness.retrieve_skill(state)
    
    assert res["status"] == TaskStatus.SKILL_LOADING
    assert res["use_skill"] is False
    assert res["skill_id"] is None
    assert res["execution_source"] == "auto"

@pytest.mark.asyncio
async def test_retrieve_skill_community(mock_dependencies):
    """測試 retrieve_skill（找到結構化 CommunitySkill 技能）"""
    harness = Harness("h-1", AgentType.HARNESS)
    mock_skill = CommunitySkill(id="yaml-skill", name="Yaml Skill", target=TargetConfig(domain="example.com"))
    mock_dependencies["memory"].retrieve_skill.return_value = mock_skill
    
    state = create_blank_state()
    res = await harness.retrieve_skill(state)
    
    assert res["status"] == TaskStatus.SKILL_LOADING
    assert res["use_skill"] is True
    assert res["skill_id"] == "yaml-skill"
    assert res["execution_source"] == "skill"
    assert res["skill_object"] is mock_skill

@pytest.mark.asyncio
async def test_retrieve_skill_auto(mock_dependencies):
    """測試 retrieve_skill（找到自動生成 JSON 格式技能）"""
    harness = Harness("h-1", AgentType.HARNESS)
    mock_skill_dict = {"id": "json-skill", "target_domain": "example.com", "code": "pass"}
    mock_dependencies["memory"].retrieve_skill.return_value = mock_skill_dict
    
    state = create_blank_state()
    res = await harness.retrieve_skill(state)
    
    assert res["status"] == TaskStatus.SKILL_LOADING
    assert res["use_skill"] is True
    assert res["skill_id"] == "json-skill"
    assert res["execution_source"] == "skill"
    assert res["skill_object"] is mock_skill_dict

@pytest.mark.asyncio
async def test_handle_error_with_llm_success(mock_dependencies):
    """測試 handle_error_with_llm（LLM 調用成功）"""
    harness = Harness("h-1", AgentType.HARNESS)
    
    # 模擬設定與 LLM 模組
    with patch("agents.harness.settings") as mock_settings, \
         patch("utils.llm_manager.analyze_error", new_callable=AsyncMock) as mock_llm_analyze:
        
        mock_settings.MAX_RETRY_COUNT = 20
        mock_llm_analyze.return_value = {
            "fields": [{"name": "price", "selector": ".price"}],
            "actions": ["wait", "click"],
            "wait_time": 5
        }
        
        state = create_blank_state()
        state["use_skill"] = True
        state["error_log"].append("Selector not found")
        
        res = await harness.handle_error_with_llm(state)
        
        assert res["status"] == TaskStatus.REFLECTING
        assert res["retry_count"] == 1
        assert res["skill_failed"] is True
        assert res["use_skill"] is False
        assert res["execution_source"] == "auto"
        assert res["current_strategy"]["fields"] == [{"name": "price", "selector": ".price"}]
        assert "1" in res["metadata"]["retry_progress"]
        mock_llm_analyze.assert_called_once()

@pytest.mark.asyncio
async def test_handle_error_with_llm_exception(mock_dependencies):
    """測試 handle_error_with_llm（LLM 拋出異常，套用預設策略）"""
    harness = Harness("h-1", AgentType.HARNESS)
    
    with patch("agents.harness.settings") as mock_settings, \
         patch("utils.llm_manager.analyze_error", new_callable=AsyncMock) as mock_llm_analyze:
        
        mock_settings.MAX_RETRY_COUNT = 20
        mock_llm_analyze.side_effect = Exception("LLM connection timeout")
        
        state = create_blank_state()
        res = await harness.handle_error_with_llm(state)
        
        assert res["status"] == TaskStatus.REFLECTING
        assert res["retry_count"] == 1
        assert res["current_strategy"]["actions"] == ["wait", "scroll"]
        assert res["current_strategy"]["wait_time"] == 3
        assert "LLM 調用失敗" in res["current_strategy"]["reason"]

@pytest.mark.asyncio
async def test_update_skill_library_case_a(mock_dependencies):
    """測試 update_skill_library 情況 A：技能一次性成功，不處理"""
    harness = Harness("h-1", AgentType.HARNESS)
    
    state = create_blank_state()
    state["use_skill"] = True
    state["skill_failed"] = False
    
    res = await harness.update_skill_library(state)
    assert res["status"] == TaskStatus.COMPLETED
    assert res["metadata"]["skill_action"] == "none"
    mock_dependencies["memory"].update_community_skill.assert_not_called()
    mock_dependencies["memory"].store_community_skill.assert_not_called()

@pytest.mark.asyncio
async def test_update_skill_library_case_b(mock_dependencies):
    """測試 update_skill_library 情況 B：技能失敗後成功，更新技能"""
    harness = Harness("h-1", AgentType.HARNESS)
    
    mock_skill = CommunitySkill(id="yaml-skill", name="Yaml Skill", target=TargetConfig(domain="example.com"))
    mock_dependencies["memory"].retrieve_skill.return_value = mock_skill
    
    state = create_blank_state()
    state["use_skill"] = True
    state["skill_failed"] = True
    state["skill_id"] = "yaml-skill"
    state["current_strategy"] = {
        "fields": [{"name": "title", "selector": "h1", "type": "text"}]
    }
    
    res = await harness.update_skill_library(state)
    assert res["status"] == TaskStatus.COMPLETED
    assert res["metadata"]["skill_action"] == "updated"
    assert len(mock_skill.extractors) == 1
    assert mock_skill.extractors[0].name == "title"
    mock_dependencies["memory"].update_community_skill.assert_called_with(mock_skill)

@pytest.mark.asyncio
async def test_update_skill_library_case_c(mock_dependencies):
    """測試 update_skill_library 情況 C：自動執行成功，保存為新技能"""
    harness = Harness("h-1", AgentType.HARNESS)
    
    mock_skill = CommunitySkill(id="generated_t1", name="generated Name", target=TargetConfig(domain="example.com"))
    mock_dependencies["gen_skill"].return_value = mock_skill
    mock_dependencies["browser"].extract_domain.return_value = "example.com"
    
    state = create_blank_state()
    state["use_skill"] = False
    state["execution_source"] = "auto"
    state["current_strategy"] = {
        "fields": [{"name": "price", "selector": ".price"}],
        "execution": {"wait_time": 2},
        "prompt": "prompt text"
    }
    
    res = await harness.update_skill_library(state)
    assert res["status"] == TaskStatus.COMPLETED
    assert res["metadata"]["skill_action"] == "created"
    assert res["skill_id"] == "generated_t1"
    
    mock_dependencies["gen_skill"].assert_called_once()
    mock_dependencies["memory"].store_community_skill.assert_called_with(mock_skill)

@pytest.mark.asyncio
async def test_reject_task(mock_dependencies):
    """測試 reject_task"""
    harness = Harness("h-1", AgentType.HARNESS)
    state = create_blank_state()
    res = await harness.reject_task(state)
    assert res["status"] == TaskStatus.REJECTED
    assert isinstance(res["end_time"], datetime)

@pytest.mark.asyncio
async def test_output_result(mock_dependencies):
    """測試 output_result"""
    harness = Harness("h-1", AgentType.HARNESS)
    
    # 1. 正常狀態完成，改為 COMPLETED
    state = create_blank_state()
    state["status"] = TaskStatus.EXECUTING
    res = await harness.output_result(state)
    assert res["status"] == TaskStatus.COMPLETED
    assert isinstance(res["end_time"], datetime)

    # 2. 失敗狀態，保持 FAILED
    state_failed = create_blank_state()
    state_failed["status"] = TaskStatus.FAILED
    res_failed = await harness.output_result(state_failed)
    assert res_failed["status"] == TaskStatus.FAILED

    # 3. 拒絕狀態，保持 REJECTED
    state_rejected = create_blank_state()
    state_rejected["status"] = TaskStatus.REJECTED
    res_rejected = await harness.output_result(state_rejected)
    assert res_rejected["status"] == TaskStatus.REJECTED

@pytest.mark.asyncio
async def test_handle_error_with_llm_missing_fields(mock_dependencies):
    """測試 handle_error_with_llm 當 LLM 返回的 strategy 字典缺少必要欄位時，自動套用預設值"""
    harness = Harness("h-1", AgentType.HARNESS)
    
    with patch("agents.harness.settings") as mock_settings, \
         patch("utils.llm_manager.analyze_error", new_callable=AsyncMock) as mock_llm_analyze:
        
        mock_settings.MAX_RETRY_COUNT = 20
        # 返回一個完全空白的 dictionary
        mock_llm_analyze.return_value = {}
        
        state = create_blank_state()
        state["use_skill"] = True
        state["error_log"].append("Selector not found")
        
        res = await harness.handle_error_with_llm(state)
        
        assert res["status"] == TaskStatus.REFLECTING
        assert res["current_strategy"]["fields"] == []
        assert res["current_strategy"]["actions"] == ["wait", "scroll"]
        assert res["current_strategy"]["wait_time"] == 3

