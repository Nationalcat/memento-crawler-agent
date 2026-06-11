"""
配置模組
定義系統的全局配置參數
使用 pydantic-settings 進行配置管理
支援從環境變數或 .env 檔案載入配置
"""
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    系統配置類別
    包含應用程式的基本配置、LLM 設定、爬蟲參數等
    """
    # 應用程式基本資訊
    APP_NAME: str = "Memento-Skills 爬蟲 Agent"  # 應用程式名稱
    VERSION: str = "1.0.0"                        # 版本號
    DEBUG: bool = True                            # 除錯模式

    # LLM 服務配置
    LLM_PROVIDER: str = "openai"       # 使用的 LLM 提供者 (openai, ollama)
    LLM_API_KEY: Optional[str] = None  # LLM API 金鑰
    LLM_MODEL: str = "gpt-4"           # 使用的 LLM 模型
    LLM_BASE_URL: Optional[str] = None # LLM API 基礎網址 (例如 Ollama 使用 http://localhost:11434/v1)

    # 爬蟲參數配置
    MAX_RETRY_COUNT: int = 20           # 最大重試次數
    BROWSER_HEADLESS: bool = True       # 無頭瀏覽器模式

    # 技能配置
    SKILLS_DATA_DIR: str = "skills/data"       # 自動生成技能目錄
    SKILLS_COMMUNITY_DIR: str = "skills/community"  # 結構化技能目錄

    # 提示詞配置
    PROMPTS_FILE: str = "prompts.yml"     # 提示詞配置檔案路徑

    # 資料庫配置
    DATABASE_URL: str = "sqlite:///memento_crawler.db" # SQLite 資料庫連線網址

    class Config:
        """Pydantic 配置"""
        env_file = ".env"  # 環境變數檔案路徑


# 建立全域配置實例
settings = Settings()
