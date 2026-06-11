"""
執行節點模組
負責網頁爬取、錯誤處理、數據解析等
"""
from models import AgentState, TaskStatus
from agents import AgentFactory, AgentType
from config import settings


async def execute_with_skill(state: AgentState) -> AgentState:
    """
    使用 Skill 執行節點
    - 從 state['skill_object'] 獲取技能
    - 使用技能的 code 和 selectors
    - 執行爬取
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    state['current_step'] = 4
    executor = AgentFactory.create(AgentType.EXECUTOR, "executor_main")
    return await executor.execute_with_skill(state)


async def execute_auto(state: AgentState) -> AgentState:
    """
    自動執行節點
    - LLM 分析網頁結構
    - 生成爬取策略
    - 執行爬取
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    state['current_step'] = 4
    executor = AgentFactory.create(AgentType.EXECUTOR, "executor_main")
    return await executor.execute_auto(state)


async def handle_error(state: AgentState) -> AgentState:
    """
    錯誤處理節點
    - 獲取最新錯誤信息
    - 生成錯誤分析提示詞
    - LLM 生成新策略
    - retry_count += 1
    - 推送「正在第 N 次重試」給前端
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    state['current_step'] = 5
    harness = AgentFactory.create(AgentType.HARNESS, "harness_main")
    return await harness.handle_error_with_llm(state)


async def parse_data(state: AgentState) -> AgentState:
    """
    解析數據節點
    - 清洗提取的原始數據
    - 轉換為結構化格式
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    state['current_step'] = 6
    state['status'] = TaskStatus.EXTRACTING

    # 如果有提取的數據，進行清洗
    if state.get('extracted_data'):
        try:
            from utils import llm_manager
            import json

            # 將提取的數據轉換為字符串
            raw_data = json.dumps(state['extracted_data'], ensure_ascii=False, default=str)

            # 調用 LLM 進行數據清洗
            cleaned_data = await llm_manager.clean_data(
                instruction=state['instruction'],
                raw_data=raw_data,
                state=state
            )

            # 如果 LLM 返回的是列表，直接使用
            if isinstance(cleaned_data, list):
                state['extracted_data'] = cleaned_data
            # 如果返回的是字典且包含 data 字段
            elif isinstance(cleaned_data, dict) and 'data' in cleaned_data:
                state['extracted_data'] = cleaned_data['data']
            # 否則保持原數據不變

        except Exception as e:
            # 清洗失敗時保持原數據，記錄警告
            state['error_log'].append(f"[數據清洗警告] {str(e)}")

    return state
