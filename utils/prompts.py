"""
提示詞載入器模組
從 YAML 配置檔案中載入提示詞模板
支援變數替換和格式化
"""
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class PromptLoader:
    """
    提示詞載入器（單例模式）
    從 prompts.yml 載入所有提示詞模板
    """
    _instance: Optional['PromptLoader'] = None
    _prompts: Dict[str, Any] = {}

    def __new__(cls):
        """單例模式實作"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_prompts()
        return cls._instance

    def _load_prompts(self):
        """載入提示詞配置檔案"""
        config_path = Path(__file__).parent.parent / "prompts.yml"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self._prompts = yaml.safe_load(f)
        else:
            self._prompts = {}

    def get_prompt(self, prompt_name: str, **kwargs) -> Dict[str, str]:
        """
        獲取並格式化提示詞
        參數:
            prompt_name: 提示詞名稱
            **kwargs: 替換變數
        回傳:
            包含 system 和 user 的字典
        """
        prompt_template = self._prompts.get(prompt_name)
        if not prompt_template:
            raise ValueError(f"提示詞 '{prompt_name}' 不存在")

        result = {}
        if 'system' in prompt_template:
            result['system'] = prompt_template['system'].format(**kwargs)
        if 'user' in prompt_template:
            result['user'] = prompt_template['user'].format(**kwargs)

        return result

    def get_system_prompt(self, prompt_name: str, **kwargs) -> str:
        """獲取系統提示詞"""
        prompt = self.get_prompt(prompt_name, **kwargs)
        return prompt.get('system', '')

    def get_user_prompt(self, prompt_name: str, **kwargs) -> str:
        """獲取用戶提示詞"""
        prompt = self.get_prompt(prompt_name, **kwargs)
        return prompt.get('user', '')

    def reload(self):
        """重新載入配置檔案"""
        self._load_prompts()

    @classmethod
    def reset(cls):
        """重置載入器（用於測試）"""
        cls._instance = None
        cls._prompts = {}


# 建立全域實例
prompt_loader = PromptLoader()
