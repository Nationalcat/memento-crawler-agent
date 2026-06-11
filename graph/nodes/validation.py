"""
驗證節點模組
負責輸入驗證、URL 可訪問性檢查、任務拒絕等
"""
from models import AgentState, TaskStatus
from agents import AgentFactory, AgentType


async def validate_input(state: AgentState) -> AgentState:
    """
    驗證輸入節點
    - 檢查 URL 是否為空
    - 檢查 instruction 是否為空
    - URL 格式補全（添加 https://）
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    state['current_step'] = 1
    harness = AgentFactory.create(AgentType.HARNESS, "harness_main")
    return await harness.validate_input(state)


async def check_url_access(state: AgentState) -> AgentState:
    """
    檢查 URL 可訪問性節點
    - 發送 HTTP HEAD 請求
    - 檢查狀態碼
    - 404/500 等標記為不可訪問
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    state['current_step'] = 2
    harness = AgentFactory.create(AgentType.HARNESS, "harness_main")
    return await harness.check_url_access(state)


async def reject_task(state: AgentState) -> AgentState:
    """
    拒絕任務節點
    - 設置狀態為 REJECTED
    - 記錄錯誤原因
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    state['current_step'] = state['total_steps']
    harness = AgentFactory.create(AgentType.HARNESS, "harness_main")
    return await harness.reject_task(state)
