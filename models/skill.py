"""
技能模型模組
定義爬蟲技能的資料結構與技能類型
技能是系統學習與累積經驗的核心單位
"""
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class SkillType(str, Enum):
    """
    技能類型列舉
    定義系統中可使用的爬蟲技能分類
    """
    NAVIGATION = "navigation"        # 導航技能：網頁跳轉、頁面導覽
    EXTRACTION = "extraction"        # 提取技能：資料抓取、內容萃取
    INTERACTION = "interaction"      # 互動技能：點擊、輸入、表單填寫
    ANTI_DETECT = "anti_detect"      # 反偵測技能：繞過反爬蟲機制
    DATA_CLEANING = "data_cleaning"  # 資料清洗技能：資料格式化與清理


class Skill(BaseModel):
    """
    技能資料模型
    儲存爬蟲技能的完整資訊，包含程式碼、選擇器、執行成功率等
    支援版本控制與自動更新時間戳記
    """
    id: str                                                    # 技能唯一識別碼
    name: str                                                  # 技能名稱
    skill_type: SkillType                                      # 技能類型
    target_domain: str                                         # 目標網站域名
    description: str                                           # 技能描述說明
    code: str                                                  # 技能執行程式碼
    selectors: Dict[str, str] = Field(default_factory=dict)    # CSS 選擇器對應表
    success_rate: float = 0.0                                  # 歷史執行成功率
    version: int = 1                                           # 技能版本號
    created_at: datetime = Field(default_factory=datetime.now) # 建立時間
    updated_at: datetime = Field(default_factory=datetime.now) # 最後更新時間
    metadata: Dict[str, Any] = Field(default_factory=dict)     # 額外元資料
