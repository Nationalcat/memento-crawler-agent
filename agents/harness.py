"""
Harness 控制層模組
實作系統的核心控制邏輯，負責：
1. 任務解析與流程規劃
2. 技能選擇與策略決策
3. 失敗反思與技能進化
是 Memento-Skills 架構中的「讀寫反思學習」核心
支援兩種技能格式：
- 結構化技能（SKILL.md 格式）
- 自動生成技能（JSON 格式）
"""
from typing import Dict, Any, Optional, Union
from datetime import datetime
from models import AgentState, TaskStatus
from skills import CommunitySkill, SkillLoaderFactory, SkillFormat, generate_skill_from_execution
from skills.memory import SkillMemory
from observers import TaskMonitor
from utils import BrowserManager, prompt_loader
from config import settings
from .factory import BaseAgent, AgentType, AgentFactory


class Harness(BaseAgent):
    """
    Harness 控制層
    繼承 BaseAgent，實作系統的核心控制邏輯
    包含技能記憶庫和任務監控器
    """

    def __init__(self, agent_id: str, agent_type: AgentType):
        """
        初始化 Harness 控制層
        參數:
            agent_id: Agent 唯一識別碼
            agent_type: Agent 類型
        """
        super().__init__(agent_id, agent_type)
        self.skill_memory = SkillMemory()           # 技能記憶庫實例
        self.monitor = TaskMonitor()                # 任務監控器實例

    async def process(self, state: AgentState) -> AgentState:
        """
        處理任務狀態
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        state['status'] = TaskStatus.PARSING
        self.monitor.update_state(state)
        return state

    async def validate_input(self, state: AgentState) -> AgentState:
        """
        驗證輸入
        - 檢查 URL 是否為空
        - 檢查 instruction 是否為空
        - URL 格式補全（添加 https://）
        
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        state['status'] = TaskStatus.PARSING
        self.monitor.update_state(state)

        url = state.get('url', '').strip()
        instruction = state.get('instruction', '').strip()

        # 檢查 URL 是否為空
        if not url:
            state['status'] = TaskStatus.REJECTED
            state['reject_reason'] = 'url_empty'
            state['error_log'].append("請提供有效的網址")
            self.monitor.update_state(state)
            return state

        # 檢查 instruction 是否為空
        if not instruction:
            state['status'] = TaskStatus.REJECTED
            state['reject_reason'] = 'instruction_empty'
            state['error_log'].append("請提供爬取指令")
            self.monitor.update_state(state)
            return state

        # URL 格式補全
        normalized_url = BrowserManager.normalize_url(url)
        state['url'] = normalized_url

        # 初始化新欄位
        state['use_skill'] = False
        state['skill_failed'] = False
        state['execution_source'] = 'none'
        state['skill_object'] = None
        state['current_strategy'] = None
        state['original_strategy'] = None
        state['reject_reason'] = None

        self.monitor.update_state(state)
        return state

    async def check_url_access(self, state: AgentState) -> AgentState:
        """
        檢查 URL 可訪問性
        - 發送 HTTP HEAD 請求
        - 檢查狀態碼
        - 404/500 等標記為不可訪問
        
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        state['status'] = TaskStatus.PARSING
        self.monitor.update_state(state)

        url = state['url']
        result = await BrowserManager.check_url_status(url)

        if not result['accessible']:
            state['status'] = TaskStatus.REJECTED
            state['reject_reason'] = 'url_inaccessible'
            state['error_log'].append(result['message'])
            state['metadata']['status_code'] = result['status_code']
            self.monitor.update_state(state)
            return state

        self.monitor.update_state(state)
        return state

    async def retrieve_skill(self, state: AgentState) -> AgentState:
        """
        檢索技能
        - 優先查找結構化技能（SKILL.md 格式）
        - 再查找自動生成技能（JSON 格式）
        - 設置 use_skill 和 skill_object
        
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        state['status'] = TaskStatus.SKILL_LOADING
        self.monitor.update_state(state)

        # 使用技能記憶庫檢索
        skill = self.skill_memory.retrieve_skill(state['url'])

        if skill:
            state['use_skill'] = True
            state['skill_failed'] = False
            state['execution_source'] = 'skill'

            # 判斷技能類型
            if isinstance(skill, CommunitySkill):
                state['skill_id'] = skill.id
                state['skill_object'] = skill
            else:
                # JSON 格式技能
                state['skill_id'] = skill.get('id')
                state['skill_object'] = skill
        else:
            state['skill_id'] = None
            state['use_skill'] = False
            state['skill_failed'] = False
            state['execution_source'] = 'auto'
            state['skill_object'] = None

        self.monitor.update_state(state)
        return state

    async def handle_error_with_llm(self, state: AgentState) -> AgentState:
        """
        錯誤處理
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
        state['status'] = TaskStatus.REFLECTING
        state['retry_count'] += 1
        self.monitor.update_state(state)

        # 標記技能失敗（如果使用技能）
        if state['use_skill']:
            state['skill_failed'] = True

        # 切換到自動執行模式
        state['execution_source'] = 'auto'
        state['use_skill'] = False

        # 獲取錯誤信息
        error_message = state['error_log'][-1] if state['error_log'] else "未知錯誤"

        # 調用 LLM 生成新策略
        try:
            from utils import llm_manager

            new_strategy = await llm_manager.analyze_error(
                url=state['url'],
                instruction=state['instruction'],
                original_strategy=state.get('original_strategy', {}),
                error_message=error_message,
                retry_count=state['retry_count'],
                max_retry=settings.MAX_RETRY_COUNT,
                state=state
            )

            # 確保策略包含必要字段
            if 'fields' not in new_strategy:
                new_strategy['fields'] = []
            if 'actions' not in new_strategy:
                new_strategy['actions'] = ['wait', 'scroll']
            if 'wait_time' not in new_strategy:
                new_strategy['wait_time'] = 3

        except Exception as e:
            # LLM 調用失敗時使用預設策略
            new_strategy = {
                "fields": [],
                "actions": ["wait", "scroll"],
                "wait_time": 3,
                "reason": f"LLM 調用失敗: {str(e)}"
            }

        state['current_strategy'] = new_strategy
        state['metadata']['retry_progress'] = f"正在第 {state['retry_count']} 次重試..."

        self.monitor.update_state(state)
        return state

    async def update_skill_library(self, state: AgentState) -> AgentState:
        """
        更新技能庫
        
        情況A：Skill 一次性成功（use_skill=True, skill_failed=False）
        → 不處理
        
        情況B：Skill 失敗後成功（use_skill=True, skill_failed=True）
        → 更新 Skill（版本 +1）
        
        情況C：自動執行成功（use_skill=False）
        → 保存為新 Skill
        
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        state['status'] = TaskStatus.COMPLETED

        # 情況A：Skill 一次性成功，不處理
        if state.get('use_skill') and not state.get('skill_failed'):
            state['metadata']['skill_action'] = 'none'
            self.monitor.update_state(state)
            return state

        # 情況B：Skill 失敗後成功，更新 Skill
        if state.get('skill_failed') and state.get('skill_id'):
            skill = self.skill_memory.retrieve_skill(state['url'])
            if skill and isinstance(skill, CommunitySkill):
                # 更新技能內容
                if state.get('current_strategy'):
                    # 更新 extractors
                    if 'fields' in state['current_strategy']:
                        from skills import Extractor
                        new_extractors = []
                        for field in state['current_strategy']['fields']:
                            new_extractors.append(Extractor(
                                name=field.get('name', ''),
                                selector=field.get('selector', ''),
                                type=field.get('type', 'text'),
                                multiple=field.get('multiple', True)
                            ))
                        skill.extractors = new_extractors

                # 版本 +1
                self.skill_memory.update_community_skill(skill)
                state['metadata']['skill_action'] = 'updated'
                state['metadata']['skill_id'] = skill.id

        # 情況C：自動執行成功，保存為新 Skill
        elif state.get('execution_source') == 'auto':
            # 生成新技能
            skill = generate_skill_from_execution(
                skill_id=f"skill_{state['task_id']}",
                skill_name=f"自動生成_{BrowserManager.extract_domain(state['url'])}",
                url=state['url'],
                instruction=state['instruction'],
                extractors=state.get('current_strategy', {}).get('fields', []),
                execution_config=state.get('current_strategy', {}).get('execution', {}),
                prompt=state.get('current_strategy', {}).get('prompt')
            )

            # 保存技能
            self.skill_memory.store_community_skill(skill)
            state['skill_id'] = skill.id
            state['metadata']['skill_action'] = 'created'
            state['metadata']['skill_id'] = skill.id

        self.monitor.update_state(state)
        return state

    async def reject_task(self, state: AgentState) -> AgentState:
        """
        拒絕任務
        - 設置狀態為 REJECTED
        - 記錄錯誤原因
        
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        state['status'] = TaskStatus.REJECTED
        state['end_time'] = datetime.now()
        self.monitor.update_state(state)
        return state

    async def output_result(self, state: AgentState) -> AgentState:
        """
        輸出結果
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
        self.monitor.update_state(state)
        return state


# 將 Harness 註冊到 Agent 工廠
AgentFactory.register(AgentType.HARNESS, Harness)
