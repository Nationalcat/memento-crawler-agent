import pytest
from datetime import datetime
from models import TaskStatus, AgentState
from observers.monitor import (
    Observer,
    Subject,
    ConsoleLogger,
    ErrorAlert,
    TaskMonitor
)

# Helper function to create a dummy AgentState
def create_dummy_state(task_id: str, status: TaskStatus, current_step: int = 1, total_steps: int = 5, error_log: list = None) -> AgentState:
    return {
        "task_id": task_id,
        "url": "https://example.com",
        "instruction": "Test instruction",
        "status": status,
        "current_step": current_step,
        "total_steps": total_steps,
        "extracted_data": [],
        "error_log": error_log or [],
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

class MockObserver(Observer):
    """用於測試的 Mock 觀察者，記錄被呼叫的次數與收到的狀態"""
    def __init__(self):
        self.call_count = 0
        self.last_received_state = None

    def update(self, state: AgentState) -> None:
        self.call_count += 1
        self.last_received_state = state

def test_subject_registration_and_notification():
    """測試 Subject 訂閱、取消訂閱與通知機制"""
    subject = Subject()
    observer1 = MockObserver()
    observer2 = MockObserver()

    # 1. 訂閱
    subject.attach(observer1)
    subject.attach(observer2)
    assert len(subject._observers) == 2

    # 重複訂閱應該被忽略
    subject.attach(observer1)
    assert len(subject._observers) == 2

    # 發布通知
    state = create_dummy_state("t1", TaskStatus.EXECUTING)
    subject.notify(state)

    # 兩者皆應收到通知
    assert observer1.call_count == 1
    assert observer1.last_received_state == state
    assert observer2.call_count == 1
    assert observer2.last_received_state == state

    # 2. 取消訂閱
    subject.detach(observer1)
    assert len(subject._observers) == 1
    
    # 再次通知，僅 observer2 應收到
    state2 = create_dummy_state("t1", TaskStatus.COMPLETED)
    subject.notify(state2)
    assert observer1.call_count == 1  # 維持不變
    assert observer2.call_count == 2
    assert observer2.last_received_state == state2

def test_console_logger_output(capsys):
    """測試 ConsoleLogger 能否格式化輸出至控制台"""
    logger = ConsoleLogger()
    state = create_dummy_state("task-123", TaskStatus.PARSING, current_step=2, total_steps=8)
    
    logger.update(state)
    
    # 獲取標準輸出
    captured = capsys.readouterr()
    assert "任務 task-123: TaskStatus.PARSING - 步驟 2/8" in captured.out

def test_error_alert_captures_failed_status():
    """測試 ErrorAlert 是否只會收集並記錄 TaskStatus.FAILED 的錯誤日誌"""
    alert = ErrorAlert()
    
    # 正常執行狀態不應該觸發錯誤紀錄
    executing_state = create_dummy_state("task-456", TaskStatus.EXECUTING)
    alert.update(executing_state)
    assert len(alert.errors) == 0

    # 失敗狀態應該記錄
    failed_state = create_dummy_state(
        "task-456", 
        TaskStatus.FAILED, 
        error_log=["Selector not found", "Connection timeout"]
    )
    alert.update(failed_state)
    assert len(alert.errors) == 1
    assert alert.errors[0]["task_id"] == "task-456"
    assert alert.errors[0]["errors"] == ["Selector not found", "Connection timeout"]
    assert "timestamp" in alert.errors[0]

def test_task_monitor_tracking():
    """測試 TaskMonitor 狀態追蹤、歷史記錄與活動任務過濾"""
    monitor = TaskMonitor()
    observer = MockObserver()
    monitor.attach(observer)

    # 更新 task-1 狀態 (PENDING)
    state_pending = create_dummy_state("task-1", TaskStatus.PENDING)
    monitor.update_state(state_pending)
    
    assert observer.call_count == 1
    assert monitor.get_task_history("task-1") == [state_pending]
    assert monitor.get_active_tasks() == ["task-1"]

    # 更新 task-1 狀態 (EXECUTING)
    state_executing = create_dummy_state("task-1", TaskStatus.EXECUTING)
    monitor.update_state(state_executing)
    assert len(monitor.get_task_history("task-1")) == 2
    assert monitor.get_active_tasks() == ["task-1"]

    # 更新 task-2 狀態 (PARSING)
    state_t2 = create_dummy_state("task-2", TaskStatus.PARSING)
    monitor.update_state(state_t2)
    assert set(monitor.get_active_tasks()) == {"task-1", "task-2"}

    # 將 task-1 設為 COMPLETED (此狀態非活動狀態)
    state_completed = create_dummy_state("task-1", TaskStatus.COMPLETED)
    monitor.update_state(state_completed)
    assert monitor.get_active_tasks() == ["task-2"]

    # 獲取未知任務歷史，應回傳空列表
    assert monitor.get_task_history("non-existent") == []

def test_observer_abc_methods():
    """測試 Observer 抽象基類的 update 方法的 pass，以達到 100% 覆蓋率"""
    class TestObserver(Observer):
        def update(self, state):
            super().update(state)
            
    to = TestObserver()
    dummy_state = create_dummy_state("test", TaskStatus.PENDING)
    to.update(dummy_state)
