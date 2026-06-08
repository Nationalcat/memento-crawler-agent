"""
結構化技能模型模組
定義社區技能的資料結構
支援 YAML 配置和提示詞模板
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Parameter(BaseModel):
    """
    輸入參數定義
    定義技能執行時需要的輸入參數
    """
    name: str                          # 參數名稱
    type: str                          # 參數類型：string, integer, boolean, array
    required: bool = False             # 是否必填
    default: Optional[Any] = None      # 預設值
    description: str = ""              # 參數描述


class TargetConfig(BaseModel):
    """
    目標配置
    定義技能適用的目標網站
    """
    domain: str                        # 目標域名
    url_patterns: List[str] = []       # URL 匹配模式


class CrawlAction(BaseModel):
    """
    爬取動作
    定義爬取過程中的互動動作
    """
    type: str                          # 動作類型：wait, scroll, click, wait_for, input
    selector: Optional[str] = None     # CSS 選擇器
    value: Optional[str] = None        # 輸入值（用於 input 動作）
    times: Optional[int] = None        # 次數（用於 scroll）
    timeout: Optional[int] = None      # 超時時間（毫秒）


class ExecutionConfig(BaseModel):
    """
    執行配置
    定義技能執行時的行為參數
    """
    wait_time: int = 2                 # 頁面等待時間（秒）
    scroll: bool = False               # 是否需要滾動
    headless: bool = True              # 是否使用無頭瀏覽器
    actions: List[CrawlAction] = []    # 執行動作列表


class Extractor(BaseModel):
    """
    資料提取器
    定義如何從網頁中提取資料
    """
    name: str                          # 提取器名稱（欄位名稱）
    selector: str                      # CSS 選擇器
    type: str                          # 提取類型：text, attribute, html, value
    required: bool = False             # 是否必填欄位
    transform: Optional[str] = None    # 資料轉換表達式（如 "replace(/[^0-9.]/g, '')"）
    regex: Optional[str] = None        # 正則表達式提取
    attribute: Optional[str] = None    # HTML 屬性名稱（用於 attribute 類型）
    multiple: bool = False             # 是否提取多個元素（列表提取）
    children: Optional[List['Extractor']] = None  # 嵌套提取器


class OutputConfig(BaseModel):
    """
    輸出配置
    定義技能的輸出格式
    """
    format: str = "json"               # 輸出格式：json, csv
    output_schema: Dict[str, str] = {} # 輸出 schema（避免與 BaseModel.schema 衝突）


class CommunitySkill(BaseModel):
    """
    結構化技能模型
    對應 SKILL.md 文件中的配置
    """
    # 基本資訊
    id: str                                            # 技能唯一識別碼
    name: str                                          # 技能名稱
    version: str = "1.0.0"                             # 版本號
    author: str = "community"                          # 作者
    description: str = ""                              # 技能描述
    tags: List[str] = []                               # 標籤

    # 目標配置
    target: TargetConfig                               # 目標網站配置

    # 參數定義
    parameters: List[Parameter] = []                   # 輸入參數列表

    # 執行配置
    execution: ExecutionConfig = ExecutionConfig()     # 執行配置

    # 提取配置
    extractors: List[Extractor] = []                   # 資料提取器列表

    # 輸出配置
    output: OutputConfig = OutputConfig()              # 輸出配置

    # 提示詞
    prompt: str = ""                                   # SKILL.md 正文部分（提示詞模板）

    # 運行時資訊（不保存到文件）
    skill_path: Optional[str] = None                   # 技能目錄路徑
    script_path: Optional[str] = None                  # helper.py 路徑
    is_auto_generated: bool = False                    # 是否為自動生成的技能


# 更新 Extractor 的遞迴引用
Extractor.model_rebuild()
