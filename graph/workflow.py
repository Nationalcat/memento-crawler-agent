"""
LangGraph 工作流模組
定義爬蟲 Agent 的完整執行流程
使用 LangGraph 的 StateGraph 建立有向無環圖（DAG）
實現任務驗證、技能檢索、執行爬取、錯誤重試、技能更新的完整流程
"""
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from models import AgentState, TaskStatus
from config import settings

# 匯入節點函數
from .nodes import (
    validate_input,
    check_url_access,
    reject_task,
    retrieve_skill,
    execute_with_skill,
    execute_auto,
    handle_error,
    parse_data,
    update_skill,
    output_result
)


class CrawlerWorkflow:
    """
    爬蟲工作流
    使用 LangGraph 建立完整的爬蟲執行流程
    
    節點說明：
    1. validate_input: 驗證輸入（URL 和 instruction）
    2. check_url_access: 檢查 URL 可訪問性
    3. reject_task: 拒絕任務（輸入無效或不可訪問）
    4. retrieve_skill: 檢索技能記憶庫
    5. execute_with_skill: 使用 Skill 執行
    6. execute_auto: 自動解析執行
    7. handle_error: 錯誤處理與重試
    8. parse_data: 解析數據
    9. update_skill: 更新技能庫
    10. output_result: 輸出結果
    """

    def __init__(self):
        """初始化工作流並建構執行圖"""
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        建構 LangGraph 工作流圖
        定義節點、邊與條件邊，形成完整的執行流程
        回傳:
            編譯後的 StateGraph 實例
        """
        # 建立狀態圖
        workflow = StateGraph(AgentState)

        # 新增節點
        workflow.add_node("validate_input", validate_input)
        workflow.add_node("check_url_access", check_url_access)
        workflow.add_node("reject_task", reject_task)
        workflow.add_node("retrieve_skill", retrieve_skill)
        workflow.add_node("execute_with_skill", execute_with_skill)
        workflow.add_node("execute_auto", execute_auto)
        workflow.add_node("handle_error", handle_error)
        workflow.add_node("parse_data", parse_data)
        workflow.add_node("update_skill", update_skill)
        workflow.add_node("output_result", output_result)

        # 設定入口節點
        workflow.set_entry_point("validate_input")

        # 固定邊
        workflow.add_edge("parse_data", "update_skill")
        workflow.add_edge("update_skill", "output_result")
        workflow.add_edge("output_result", END)
        workflow.add_edge("reject_task", END)

        # 條件邊：驗證輸入
        workflow.add_conditional_edges(
            "validate_input",
            self._check_validation,
            {"pass": "check_url_access", "fail": "reject_task"}
        )

        # 條件邊：檢查 URL 可訪問性
        workflow.add_conditional_edges(
            "check_url_access",
            self._check_accessibility,
            {"accessible": "retrieve_skill", "inaccessible": "reject_task"}
        )

        # 條件邊：是否有技能
        workflow.add_conditional_edges(
            "retrieve_skill",
            self._has_skill,
            {"has_skill": "execute_with_skill", "no_skill": "execute_auto"}
        )

        # 條件邊：Skill 執行結果
        workflow.add_conditional_edges(
            "execute_with_skill",
            self._check_execution,
            {"success": "parse_data", "fail": "handle_error"}
        )

        # 條件邊：自動執行結果
        workflow.add_conditional_edges(
            "execute_auto",
            self._check_execution,
            {"success": "parse_data", "fail": "handle_error"}
        )

        # 條件邊：是否重試
        workflow.add_conditional_edges(
            "handle_error",
            self._should_retry,
            {"retry": "execute_auto", "exceed": "output_result"}
        )

        return workflow.compile()

    # ====== 條件判斷函數 ======

    def _check_validation(self, state: AgentState) -> str:
        """判斷驗證是否通過"""
        return "fail" if state['status'] == TaskStatus.REJECTED else "pass"

    def _check_accessibility(self, state: AgentState) -> str:
        """判斷 URL 是否可訪問"""
        return "inaccessible" if state['status'] == TaskStatus.REJECTED else "accessible"

    def _has_skill(self, state: AgentState) -> str:
        """判斷是否有匹配的技能"""
        return "has_skill" if state.get('use_skill') and state.get('skill_object') else "no_skill"

    def _check_execution(self, state: AgentState) -> str:
        """判斷執行是否成功"""
        return "fail" if state['status'] == TaskStatus.FAILED else "success"

    def _should_retry(self, state: AgentState) -> str:
        """判斷是否需要重試"""
        return "retry" if state['retry_count'] < settings.MAX_RETRY_COUNT else "exceed"

    # ====== 主入口 ======

    async def run(self, url: str, instruction: str) -> AgentState:
        """
        執行工作流（主入口）
        參數:
            url: 目標網址
            instruction: 使用者指令
        回傳:
            最終的 Agent 狀態
        """
        from datetime import datetime
        import uuid

        initial_state: AgentState = {
            "task_id": str(uuid.uuid4()),
            "url": url,
            "instruction": instruction,
            "status": TaskStatus.PENDING,
            "current_step": 0,
            "total_steps": 10,
            "extracted_data": [],
            "error_log": [],
            "skill_id": None,
            "use_skill": False,
            "skill_failed": False,
            "execution_source": "none",
            "skill_object": None,
            "retry_count": 0,
            "start_time": datetime.now(),
            "end_time": None,
            "metadata": {},
            "current_strategy": None,
            "original_strategy": None,
            "reject_reason": None
        }

        return await self.graph.ainvoke(initial_state)
