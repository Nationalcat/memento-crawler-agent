"""
技能節點模組
負責技能檢索、技能庫更新等
"""
from models import AgentState, TaskStatus
from agents import AgentFactory, AgentType


async def retrieve_skill(state: AgentState) -> AgentState:
    """
    檢索技能節點
    - 根據 URL 域名查找匹配的 Skill
    - 設置 use_skill 和 skill_object
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    harness = AgentFactory.create(AgentType.HARNESS, "harness_main")
    return await harness.retrieve_skill(state)


async def update_skill(state: AgentState) -> AgentState:
    """
    更新技能庫節點
    
    情況A：Skill 一次性成功（use_skill=True, skill_failed=False）
    → 不處理
    
    情況B：Skill 失敗後成功（use_skill=True, skill_failed=True）
    → 更新 Skill
    
    情況C：自動執行成功（use_skill=False）
    → 保存為新 Skill
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    harness = AgentFactory.create(AgentType.HARNESS, "harness_main")
    return await harness.update_skill_library(state)
