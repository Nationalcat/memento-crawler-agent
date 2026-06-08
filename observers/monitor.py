"""
觀察者模式模組
實作任務狀態監控與事件通知機制
透過觀察者模式實現系統各元件間的鬆耦合通訊
支援控制台日誌輸出與錯誤告警等功能
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from models import AgentState, TaskStatus


class Observer(ABC):
    """
    觀察者抽象基類
    定義所有觀察者必須實作的更新方法
    """

    @abstractmethod
    def update(self, state: AgentState) -> None:
        """
        接收狀態更新通知
        參數:
            state: 當前 Agent 狀態
        """
        pass


class Subject:
    """
    被觀察主題基類
    管理觀察者的訂閱與通知機制
    """

    def __init__(self):
        """初始化觀察者列表"""
        self._observers: List[Observer] = []

    def attach(self, observer: Observer) -> None:
        """
        附加觀察者（訂閱）
        參數:
            observer: 要附加的觀察者實例
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """
        分離觀察者（取消訂閱）
        參數:
            observer: 要分離的觀察者實例
        """
        self._observers.remove(observer)

    def notify(self, state: AgentState) -> None:
        """
        通知所有觀察者
        參數:
            state: 當前 Agent 狀態
        """
        for observer in self._observers:
            observer.update(state)


class ConsoleLogger(Observer):
    """
    控制台日誌觀察者
    將任務狀態變更輸出到控制台，用於即時監控
    """

    def update(self, state: AgentState) -> None:
        """輸出格式化的狀態日誌到控制台"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 任務 {state['task_id']}: {state['status']} - 步驟 {state['current_step']}/{state['total_steps']}")


class ErrorAlert(Observer):
    """
    錯誤告警觀察者
    收集並記錄任務執行過程中的錯誤資訊
    """

    def __init__(self):
        """初始化錯誤記錄列表"""
        self.errors: List[Dict[str, Any]] = []

    def update(self, state: AgentState) -> None:
        """當任務失敗時記錄錯誤資訊"""
        if state['status'] == TaskStatus.FAILED:
            self.errors.append({
                "task_id": state['task_id'],          # 任務 ID
                "timestamp": datetime.now().isoformat(),  # 錯誤發生時間
                "errors": state['error_log']           # 錯誤詳細記錄
            })


class TaskMonitor(Subject):
    """
    任務監控器
    繼承 Subject 類別，提供任務狀態追蹤與歷史記錄功能
    是觀察者模式的核心管理類別
    """

    def __init__(self):
        """初始化任務歷史記錄"""
        super().__init__()
        self.task_history: Dict[str, List[AgentState]] = {}  # 任務 ID -> 狀態歷史

    def update_state(self, state: AgentState) -> None:
        """
        更新任務狀態並通知所有觀察者
        參數:
            state: 新的 Agent 狀態
        """
        task_id = state['task_id']
        if task_id not in self.task_history:
            self.task_history[task_id] = []
        self.task_history[task_id].append(state)
        self.notify(state)  # 通知所有訂閱的觀察者

    def get_task_history(self, task_id: str) -> List[AgentState]:
        """
        獲取指定任務的狀態歷史
        參數:
            task_id: 任務識別碼
        回傳:
            該任務的所有狀態記錄列表
        """
        return self.task_history.get(task_id, [])

    def get_active_tasks(self) -> List[str]:
        """
        獲取所有正在執行中的任務 ID
        回傳:
            處於活動狀態的任務 ID 列表
        """
        active_statuses = {TaskStatus.PENDING, TaskStatus.EXECUTING, TaskStatus.PARSING}
        return [
            task_id for task_id, states in self.task_history.items()
            if states and states[-1]['status'] in active_statuses
        ]
