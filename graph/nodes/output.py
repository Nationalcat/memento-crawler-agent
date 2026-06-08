"""
輸出節點模組
負責最終結果輸出
"""
from models import AgentState, TaskStatus
from agents import AgentFactory, AgentType
from datetime import datetime


async def output_result(state: AgentState) -> AgentState:
    """
    輸出結果節點
    - 設置結束時間
    - 確保狀態正確
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    if state['status'] not in [TaskStatus.FAILED, TaskStatus.REJECTED]:
        state['status'] = TaskStatus.COMPLETED

    state['end_time'] = datetime.now()
    return state
