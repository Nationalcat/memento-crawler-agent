"""
Agent 執行層模組
負責實際的網頁互動與資料抓取操作
包含瀏覽器管理、頁面導航、資料提取等功能
是 Memento-Skills 架構中的執行單元
支援兩種執行模式：
1. 使用結構化技能執行（SKILL.md 格式）
2. 自動解析執行（LLM 生成策略）
"""
from typing import Dict, Any
from models import AgentState, TaskStatus
from skills import (
    CommunitySkill, CommunitySkillExecutor, 
    SkillLoaderFactory, SkillFormat, generate_skill_from_execution
)
from skills.memory import SkillMemory
from utils import BrowserManager, prompt_loader
from observers import TaskMonitor
from config import settings
from .factory import BaseAgent, AgentType, AgentFactory


class ExecutorAgent(BaseAgent):
    """
    Agent 執行層
    繼承 BaseAgent，實作具體的網頁互動與資料抓取邏輯
    支援兩種執行模式：結構化技能執行和自動執行
    """

    def __init__(self, agent_id: str, agent_type: AgentType):
        """
        初始化執行層 Agent
        參數:
            agent_id: Agent 唯一識別碼
            agent_type: Agent 類型
        """
        super().__init__(agent_id, agent_type)
        self.browser = BrowserManager()  # 瀏覽器管理器
        self.monitor = TaskMonitor()     # 任務監控器

    async def process(self, state: AgentState) -> AgentState:
        """
        處理任務執行（根據 execution_source 決定執行模式）
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        if state.get('execution_source') == 'skill' and state.get('skill_object'):
            return await self.execute_with_skill(state)
        else:
            return await self.execute_auto(state)

    async def execute_with_skill(self, state: AgentState) -> AgentState:
        """
        使用結構化技能執行
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        state['status'] = TaskStatus.EXECUTING
        self.monitor.update_state(state)

        skill_data = state.get('skill_object', {})

        try:
            # 判斷技能類型
            if isinstance(skill_data, CommunitySkill):
                # 結構化技能
                return await self._execute_community_skill(state, skill_data)
            elif isinstance(skill_data, dict):
                # 自動生成技能（JSON 格式）
                return await self._execute_auto_skill(state, skill_data)
            else:
                raise ValueError(f"不支援的技能類型: {type(skill_data)}")

        except Exception as e:
            # 發生異常時記錄錯誤
            state['error_log'].append(f"[Skill執行錯誤] {str(e)}")
            state['status'] = TaskStatus.FAILED

        # 通知監控器狀態更新
        self.monitor.update_state(state)
        return state

    async def _execute_community_skill(self, state: AgentState, skill: CommunitySkill) -> AgentState:
        """
        執行結構化技能
        參數:
            state: 當前 Agent 狀態
            skill: 結構化技能實例
        回傳:
            更新後的 Agent 狀態
        """
        # 創建執行器
        executor = CommunitySkillExecutor(skill)

        # 初始化瀏覽器
        await self.browser.initialize()

        try:
            # 導航至目標網址
            await self.browser.navigate(state['url'])

            # 執行爬取動作
            for action in skill.execution.actions:
                await self._execute_action(action)

            # 獲取頁面內容
            page_content = await self.browser.get_content()

            # 使用提取器提取資料
            extracted = executor.extract_data(page_content)
            state['extracted_data'] = extracted

            # 任務完成
            state['status'] = TaskStatus.COMPLETED

        finally:
            # 確保瀏覽器資源被釋放
            await self.browser.close()

        # 通知監控器狀態更新
        self.monitor.update_state(state)
        return state

    async def _execute_auto_skill(self, state: AgentState, skill_data: Dict) -> AgentState:
        """
        執行自動生成技能（JSON 格式）
        參數:
            state: 當前 Agent 狀態
            skill_data: 技能數據
        回傳:
            更新後的 Agent 狀態
        """
        # 初始化瀏覽器
        await self.browser.initialize()

        try:
            # 導航至目標網址
            page_content = await self.browser.navigate(state['url'])

            # 使用選擇器提取資料
            selectors = skill_data.get('selectors', {})
            extracted = await self._extract_with_selectors(page_content, selectors, state)
            state['extracted_data'] = extracted

            # 任務完成
            state['status'] = TaskStatus.COMPLETED

        finally:
            # 確保瀏覽器資源被釋放
            await self.browser.close()

        # 通知監控器狀態更新
        self.monitor.update_state(state)
        return state

    async def execute_auto(self, state: AgentState) -> AgentState:
        """
        自動執行（LLM 生成策略）
        參數:
            state: 當前 Agent 狀態
        回傳:
            更新後的 Agent 狀態
        """
        state['status'] = TaskStatus.EXECUTING
        self.monitor.update_state(state)

        try:
            # 初始化瀏覽器實例
            await self.browser.initialize()

            # 導航至目標網址
            page_content = await self.browser.navigate(state['url'])

            # 生成分析提示詞
            prompts = prompt_loader.get_prompt(
                'analyze_webpage',
                url=state['url'],
                instruction=state['instruction'],
                content=page_content[:2000]  # 限制內容長度
            )

            # 調用 LLM 生成策略
            try:
                from utils import llm_manager

                strategy = await llm_manager.analyze_webpage(
                    url=state['url'],
                    instruction=state['instruction'],
                    content=page_content,
                    state=state
                )

                # 確保策略包含必要字段
                if 'fields' not in strategy:
                    strategy['fields'] = []
                if 'actions' not in strategy:
                    strategy['actions'] = ['scroll']

            except Exception as llm_error:
                # LLM 調用失敗時使用預設策略
                strategy = {
                    "fields": [
                        {"name": "title", "selector": "h1", "type": "text"},
                        {"name": "content", "selector": "p", "type": "text"}
                    ],
                    "actions": ["scroll"],
                    "format": "json",
                    "llm_error": str(llm_error)
                }

            # 保存策略
            state['current_strategy'] = strategy
            if not state.get('original_strategy'):
                state['original_strategy'] = strategy

            # 設定狀態為提取中
            state['status'] = TaskStatus.EXTRACTING
            self.monitor.update_state(state)

            # 使用策略提取資料
            extracted = await self._extract_with_strategy(page_content, strategy, state)
            state['extracted_data'] = extracted

            # 任務完成
            state['status'] = TaskStatus.COMPLETED

        except Exception as e:
            # 發生異常時記錄錯誤
            state['error_log'].append(f"[自動執行錯誤] {str(e)}")
            state['status'] = TaskStatus.FAILED

        finally:
            # 確保瀏覽器資源被釋放
            await self.browser.close()

        # 通知監控器狀態更新
        self.monitor.update_state(state)
        return state

    async def _execute_action(self, action):
        """
        執行爬取動作
        參數:
            action: 動作配置
        """
        if action.type == "wait":
            await self.browser.wait(action.timeout or 1000)
        elif action.type == "scroll":
            for _ in range(action.times or 1):
                await self.browser.scroll()
        elif action.type == "click" and action.selector:
            await self.browser.click(action.selector)
        elif action.type == "wait_for" and action.selector:
            await self.browser.wait_for_element(action.selector, action.timeout or 10000)
        elif action.type == "input" and action.selector:
            await self.browser.input(action.selector, action.value or "")

    async def _extract_with_selectors(self, content: str, selectors: Dict, state: AgentState) -> list:
        """
        使用選擇器提取資料
        參數:
            content: 網頁原始內容
            selectors: CSS 選擇器對應表
            state: 當前 Agent 狀態
        回傳:
            提取的資料列表
        """
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        soup = BeautifulSoup(content, 'html.parser')
        results = []
        
        extracted_fields = {}
        max_len = 0
        for name, selector in selectors.items():
            if not selector:
                continue
            elements = soup.select(selector)
            values = []
            for el in elements:
                if el.name == 'img':
                    val = el.get('src') or el.get('data-src') or el.get_text(strip=True)
                elif el.name == 'a':
                    val = el.get('href') or el.get_text(strip=True)
                    if val and isinstance(val, str) and not val.startswith('http'):
                        val = urljoin(state['url'], val)
                else:
                    val = el.get_text(strip=True)
                if val:
                    values.append(val)
            extracted_fields[name] = values
            max_len = max(max_len, len(values))
            
        if max_len > 0:
            for i in range(max_len):
                item = {}
                for name, values in extracted_fields.items():
                    if i < len(values):
                        item[name] = values[i]
                    else:
                        item[name] = None
                results.append(item)
                
        return results

    async def _extract_with_strategy(self, content: str, strategy: Dict, state: AgentState) -> list:
        """
        使用策略提取資料
        參數:
            content: 網頁原始內容
            strategy: 執行策略
            state: 當前 Agent 狀態
        回傳:
            提取的資料列表
        """
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        soup = BeautifulSoup(content, 'html.parser')
        fields = strategy.get('fields', [])
        results = []
        
        extracted_fields = {}
        max_len = 0
        for field in fields:
            name = field.get('name')
            selector = field.get('selector')
            field_type = field.get('type', 'text')
            
            if not name or not selector:
                continue
                
            elements = soup.select(selector)
            values = []
            for el in elements:
                if field_type == 'image' or field_type == '圖片':
                    val = el.get('src') or el.get('data-src') or el.get_text(strip=True)
                elif field_type == 'link' or field_type == '連結':
                    val = el.get('href') or el.get_text(strip=True)
                    if val and isinstance(val, str) and not val.startswith('http'):
                        val = urljoin(state['url'], val)
                else:
                    val = el.get_text(strip=True)
                if val:
                    values.append(val)
            
            extracted_fields[name] = values
            max_len = max(max_len, len(values))
            
        if max_len > 0:
            for i in range(max_len):
                item = {}
                for name, values in extracted_fields.items():
                    if i < len(values):
                        item[name] = values[i]
                    else:
                        item[name] = None
                results.append(item)
            
        return results

    async def save_skill_from_execution(self, state: AgentState) -> None:
        """
        從執行結果保存技能
        參數:
            state: 當前 Agent 狀態
        """
        if state['status'] != TaskStatus.COMPLETED:
            return

        # 生成技能
        skill = generate_skill_from_execution(
            skill_id=f"skill_{state['task_id']}",
            skill_name=f"自動生成_{state['url']}",
            url=state['url'],
            instruction=state['instruction'],
            extractors=state.get('current_strategy', {}).get('fields', []),
            execution_config=state.get('current_strategy', {}).get('execution', {}),
            prompt=state.get('current_strategy', {}).get('prompt')
        )

        # 保存技能
        memory = SkillMemory()
        memory.store_community_skill(skill)

        # 更新狀態
        state['skill_id'] = skill.id
        state['metadata']['skill_action'] = 'created'
        state['metadata']['skill_id'] = skill.id


# 將 ExecutorAgent 註冊到 Agent 工廠
AgentFactory.register(AgentType.EXECUTOR, ExecutorAgent)
