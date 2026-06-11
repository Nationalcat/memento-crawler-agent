"""
LLM 工具模組
提供 LLM 調用的統一介面
使用工廠模式與轉接器模式支援不同 LLM 提供者 (OpenAI, Ollama)
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings
from .prompts import prompt_loader


class LLMAdapter(ABC):
    """
    LLM 適配器抽象介面 (Adapter Pattern)
    定義所有 LLM 提供者必須實現的統一介面
    """
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """調用 LLM 生成回覆"""
        pass


class OpenAIAdapter(LLMAdapter):
    """
    OpenAI API 適配器 (Concrete Adapter)
    """
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        self._llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.1,
            max_tokens=1024,
            timeout=90.0
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        response = await self._llm.ainvoke(messages)
        return response.content


class OllamaAdapter(LLMAdapter):
    """
    Ollama API 適配器 (Concrete Adapter)
    利用 Ollama 的 OpenAI 相容端點進行呼叫
    """
    def __init__(self, model: str, base_url: Optional[str] = None):
        # Ollama 本地端不需要 API key，但 ChatOpenAI 要求非空字串，故代入 "ollama"
        self._llm = ChatOpenAI(
            model=model,
            api_key="ollama",
            base_url=base_url or "http://localhost:11434/v1",
            temperature=0.1,
            max_tokens=1024,
            timeout=90.0
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        response = await self._llm.ainvoke(messages)
        return response.content


class LLMFactory:
    """
    LLM 適配器工廠 (Simple Factory Pattern)
    負責依據配置建立並返回對應的 LLMAdapter 實例
    """
    @staticmethod
    def get_adapter(provider: str) -> Optional[LLMAdapter]:
        provider_lower = provider.lower()
        if provider_lower == "openai":
            if not settings.LLM_API_KEY:
                return None
            return OpenAIAdapter(
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL
            )
        elif provider_lower == "ollama":
            return OllamaAdapter(
                model=settings.LLM_MODEL,
                base_url=settings.LLM_BASE_URL
            )
        else:
            raise ValueError(f"未支援的 LLM 提供者: {provider}")


class LLMManager:
    """
    LLM 管理器（單例模式）
    提供統一的 LLM 調用介面，內部透過 Adapter 進行調用
    """
    _instance: Optional['LLMManager'] = None
    _adapter: Optional[LLMAdapter] = None
    _llm: Optional[ChatOpenAI] = None

    def __new__(cls):
        """單例模式實作"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_llm()
        return cls._instance

    def _init_llm(self):
        """初始化 LLM"""
        try:
            self._adapter = LLMFactory.get_adapter(settings.LLM_PROVIDER)
            if self._adapter:
                self._llm = self._adapter._llm
            else:
                self._llm = None
        except ValueError:
            self._adapter = None
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

        # 若 _llm 沒有被外部 Mock 或變更，且 _adapter 存在，則使用轉接器呼叫
        if self._adapter and self._adapter._llm is self._llm:
            return await self._adapter.generate(system_prompt, user_prompt)
        else:
            # 支援 Mock 測試與回退模式的直接呼叫
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

    def _record_prompt(self, state: Optional[Dict[str, Any]], prompt_type: str, prompts_dict: Dict[str, str], response: Any) -> None:
        if state is not None:
            from datetime import datetime
            if 'prompts' not in state:
                state['prompts'] = []
            state['prompts'].append({
                "type": prompt_type,
                "system": prompts_dict.get('system', ''),
                "user": prompts_dict.get('user', ''),
                "response": json.dumps(response, ensure_ascii=False, indent=2) if isinstance(response, dict) else str(response),
                "timestamp": datetime.now().isoformat()
            })

    async def analyze_webpage(self, url: str, instruction: str, content: str, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        分析網頁結構，生成爬取策略
        參數:
            url: 目標網址
            instruction: 用戶指令
            content: 網頁內容
            state: 當前 Agent 狀態（可選）
        回傳:
            爬取策略
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # 1. 移除基本的無關內容標籤
            for tag in soup(['script', 'style', 'head', 'meta', 'link', 'noscript', 'iframe', 'svg']):
                tag.decompose()
                
            # 2. 移除常用的版面佈局標籤
            for tag in soup(['nav', 'header', 'footer']):
                tag.decompose()
                
            # 3. 移除 class 或 id 中包含側邊欄、導覽列、頁首頁尾等關鍵字的標籤
            to_decompose = []
            for tag in soup.find_all(True):
                id_val = tag.get('id', '').lower()
                class_val = ' '.join(tag.get('class', [])).lower() if tag.get('class') else ''
                if any(p in id_val or p in class_val for p in ['sidebar', 'side-bar', 'header', 'footer', 'navbar', 'menu-drawer', 'main-header']):
                    to_decompose.append(tag)
                    
            for tag in to_decompose:
                try:
                    tag.decompose()
                except Exception:
                    pass
                    
            # 4. 保留關鍵屬性，移除其他無關屬性以縮減 HTML 體積
            allowed_attrs = {'class', 'id', 'href', 'src'}
            for tag in soup.find_all(True):
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr not in allowed_attrs:
                        del tag.attrs[attr]
                    
            clean_content = str(soup)
        except Exception:
            clean_content = content

        prompts = prompt_loader.get_prompt(
            'analyze_webpage',
            url=url,
            instruction=instruction,
            content=clean_content[:5000]  # 限制內容長度為 5000 字元以防止 Ollama 內容超載
        )

        try:
            response = await self.generate_json(prompts['system'], prompts['user'])
            self._record_prompt(state, 'analyze_webpage', prompts, response)
            return response
        except Exception as e:
            self._record_prompt(state, 'analyze_webpage', prompts, f"LLM 呼叫失敗: {str(e)}")
            raise

    async def analyze_error(
        self,
        url: str,
        instruction: str,
        original_strategy: Dict,
        error_message: str,
        retry_count: int,
        max_retry: int,
        state: Optional[Dict[str, Any]] = None
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
            state: 當前 Agent 狀態（可選）
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

        try:
            response = await self.generate_json(prompts['system'], prompts['user'])
            self._record_prompt(state, 'analyze_error', prompts, response)
            return response
        except Exception as e:
            self._record_prompt(state, 'analyze_error', prompts, f"LLM 呼叫失敗: {str(e)}")
            raise

    async def clean_data(self, instruction: str, raw_data: str, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        清洗數據
        參數:
            instruction: 用戶指令
            raw_data: 原始數據
            state: 當前 Agent 狀態（可選）
        回傳:
            清洗後的數據
        """
        prompts = prompt_loader.get_prompt(
            'clean_data',
            instruction=instruction,
            raw_data=raw_data[:3000]  # 限制內容長度
        )

        try:
            response = await self.generate_json(prompts['system'], prompts['user'])
            self._record_prompt(state, 'clean_data', prompts, response)
            return response
        except Exception as e:
            self._record_prompt(state, 'clean_data', prompts, f"LLM 呼叫失敗: {str(e)}")
            raise

    async def generate_skill(
        self,
        url: str,
        instruction: str,
        strategy: Dict,
        result: Dict,
        state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成技能
        參數:
            url: 目標網址
            instruction: 用戶指令
            strategy: 執行策略
            result: 執行結果
            state: 當前 Agent 狀態（可選）
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

        try:
            response = await self.generate_json(prompts['system'], prompts['user'])
            self._record_prompt(state, 'generate_skill', prompts, response)
            return response
        except Exception as e:
            self._record_prompt(state, 'generate_skill', prompts, f"LLM 呼叫失敗: {str(e)}")
            raise


# 建立全域實例
llm_manager = LLMManager()
