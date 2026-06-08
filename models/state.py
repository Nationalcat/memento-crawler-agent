"""
狀態模型模組
定義 Agent 執行過程中的狀態結構與任務狀態列舉
用於 LangGraph 工作流中傳遞和追蹤任務進度
"""
from typing import TypedDict, List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    """
    任務狀態列舉
    定義爬蟲任務在執行生命週期中的所有可能狀態
    """
    PENDING = "pending"          # 待處理：任務已建立但尚未開始執行
    PARSING = "parsing"          # 解析中：正在解析使用者指令與目標網址
    SKILL_LOADING = "skill_loading"  # 技能載入中：正在從技能記憶庫中檢索合適的爬蟲技能
    EXECUTING = "executing"      # 執行中：Agent 正在與網頁進行互動並抓取資料
    EXTRACTING = "extracting"    # 提取中：正在從網頁內容中提取結構化資料
    REFLECTING = "reflecting"    # 反思中：正在分析執行失敗原因並生成新技能
    COMPLETED = "completed"      # 已完成：任務成功執行完畢
    FAILED = "failed"            # 已失敗：任務執行過程中發生無法恢復的錯誤
    REJECTED = "rejected"        # 已拒絕：任務因輸入無效或頁面不可訪問而被拒絕


class AgentState(TypedDict):
    """
    Agent 狀態結構
    定義在 LangGraph 工作流中傳遞的完整狀態資訊
    包含任務執行所需的所有上下文資料
    """
    # 基本資訊
    task_id: str                          # 任務唯一識別碼
    url: str                              # 目標網站網址
    instruction: str                      # 使用者的自然語言指令
    status: TaskStatus                    # 當前任務狀態
    current_step: int                     # 當前執行步驟編號
    total_steps: int                      # 總步驟數量

    # 資料相關
    extracted_data: List[Dict[str, Any]]  # 已提取的結構化資料列表
    error_log: List[str]                  # 錯誤記錄列表

    # 技能相關（新增）
    skill_id: Optional[str]               # 當前使用的技能 ID（若有）
    use_skill: bool                       # 是否使用技能執行
    skill_failed: bool                    # 技能是否執行失敗過
    execution_source: str                 # 執行來源："skill" / "auto" / "none"
    skill_object: Optional[Dict]          # 技能物件（用於傳遞給執行器）

    # 執行控制
    retry_count: int                      # 已重試次數
    start_time: datetime                  # 任務開始時間
    end_time: Optional[datetime]          # 任務結束時間（若已完成）
    metadata: Dict[str, Any]              # 額外的元資料

    # 執行策略（新增）
    current_strategy: Optional[Dict]      # 當前執行策略
    original_strategy: Optional[Dict]     # 原始執行策略（用於錯誤分析）
    reject_reason: Optional[str]          # 拒絕原因（若被拒絕）
