"""
LLM 工具模組
提供 LLM 調用的統一介面
使用 langchain-openai 進行 LLM 調用
"""
import json
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings
from .prompts import prompt_loader


class LLMManager:
    """
    LLM 管理器（單例模式）
    提供統一的 LLM 調用介面
    """
    _instance: Optional['LLMManager'] = None
    _llm: Optional[ChatOpenAI] = None

    def __new__(cls):
        """單例模式實作"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_llm()
        return cls._instance

    def _init_llm(self):
        """初始化 LLM"""
        if settings.LLM_API_KEY:
            self._llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                temperature=0.7
            )
        else:
            self._llm = None

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        調用 LLM 生成回覆
        參數:
            system_prompt: 系統提示詞
            user_prompt: 用戶提示詞
        回傳:
            LLM 回覆文本
        """
        if not self._llm:
            raise ValueError("LLM 未初始化，請設置 LLM_API_KEY")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await self._llm.ainvoke(messages)
        return response.content

    async def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        調用 LLM 生成 JSON 格式回覆
        參數:
            system_prompt: 系統提示詞
            user_prompt: 用戶提示詞
        回傳:
            解析後的 JSON 字典
        """
        response = await self.generate(system_prompt, user_prompt)

        # 嘗試提取 JSON 內容
        try:
            # 移除 markdown 代碼塊標記
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)
        except json.JSONDecodeError:
            # 如果無法解析 JSON，返回原始文本
            return {"raw_response": response}

    async def analyze_webpage(self, url: str, instruction: str, content: str) -> Dict[str, Any]:
        """
        分析網頁結構，生成爬取策略
        參數:
            url: 目標網址
            instruction: 用戶指令
            content: 網頁內容
        回傳:
            爬取策略
        """
        prompts = prompt_loader.get_prompt(
            'analyze_webpage',
            url=url,
            instruction=instruction,
            content=content[:3000]  # 限制內容長度
        )

        return await self.generate_json(prompts['system'], prompts['user'])

    async def analyze_error(
        self,
        url: str,
        instruction: str,
        original_strategy: Dict,
        error_message: str,
        retry_count: int,
        max_retry: int
    ) -> Dict[str, Any]:
        """
        分析錯誤原因，生成新策略
        參數:
            url: 目標網址
            instruction: 用戶指令
            original_strategy: 原始策略
            error_message: 錯誤信息
            retry_count: 當前重試次數
            max_retry: 最大重試次數
        回傳:
            新的執行策略
        """
        prompts = prompt_loader.get_prompt(
            'analyze_error',
            url=url,
            instruction=instruction,
            original_strategy=json.dumps(original_strategy, ensure_ascii=False, indent=2),
            error_message=error_message,
            retry_count=retry_count,
            max_retry=max_retry
        )

        return await self.generate_json(prompts['system'], prompts['user'])

    async def clean_data(self, instruction: str, raw_data: str) -> Dict[str, Any]:
        """
        清洗數據
        參數:
            instruction: 用戶指令
            raw_data: 原始數據
        回傳:
            清洗後的數據
        """
        prompts = prompt_loader.get_prompt(
            'clean_data',
            instruction=instruction,
            raw_data=raw_data[:3000]  # 限制內容長度
        )

        return await self.generate_json(prompts['system'], prompts['user'])

    async def generate_skill(
        self,
        url: str,
        instruction: str,
        strategy: Dict,
        result: Dict
    ) -> Dict[str, Any]:
        """
        生成技能
        參數:
            url: 目標網址
            instruction: 用戶指令
            strategy: 執行策略
            result: 執行結果
        回傳:
            技能配置
        """
        from utils import BrowserManager
        domain = BrowserManager.extract_domain(url)

        prompts = prompt_loader.get_prompt(
            'generate_skill',
            url=url,
            site_type=domain,
            strategy=json.dumps(strategy, ensure_ascii=False, indent=2),
            result=json.dumps(result, ensure_ascii=False, indent=2)
        )

        return await self.generate_json(prompts['system'], prompts['user'])


# 建立全域實例
llm_manager = LLMManager()
