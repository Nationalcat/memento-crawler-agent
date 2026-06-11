import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket
from api.session import SessionManager, Session

@pytest.fixture(autouse=True)
def clean_sessions():
    """每個測試執行前/後，重置 SessionManager 的狀態"""
    SessionManager.reset()
    yield
    SessionManager.reset()

def test_singleton_pattern():
    """測試 SessionManager 是否為單例模式"""
    manager1 = SessionManager()
    manager2 = SessionManager()
    assert manager1 is manager2

def test_create_session():
    """測試會話的建立"""
    manager = SessionManager()
    session_id = manager.create_session()
    
    # 確保產生的 session_id 是有效的
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    
    # 確保 Session 在管理器的資料字典中
    assert session_id in manager._sessions
    session = manager._sessions[session_id]
    assert isinstance(session, Session)
    assert session.session_id == session_id
    assert session.is_connected is False
    assert len(session.task_history) == 0

def test_get_session_and_activity_update():
    """測試獲取會話以及最後活動時間的自動更新"""
    manager = SessionManager()
    session_id = manager.create_session()
    session = manager.get_session(session_id)
    
    initial_last_active = session.last_active
    
    # 稍微模擬時間差，手動修改 last_active
    session.last_active = datetime.now() - timedelta(seconds=10)
    
    # 再次獲取
    retrieved_session = manager.get_session(session_id)
    assert retrieved_session is session
    # 檢查 last_active 有被更新為目前時間（大於修改後的時間）
    assert retrieved_session.last_active > initial_last_active

    # 獲取不存在的會話應回傳 None
    assert manager.get_session("non-existent") is None

def test_update_session_state_and_history():
    """測試更新會話狀態與任務歷史紀錄"""
    manager = SessionManager()
    session_id = manager.create_session()
    
    # 1. 更新會話狀態
    state_data = {"task_id": "t1", "status": "executing"}
    manager.update_session_state(session_id, state_data)
    
    session = manager.get_session(session_id)
    assert session.current_state == state_data

    # 2. 新增任務歷史
    task_data = {"url": "https://example.com", "result": "success"}
    manager.add_task_to_history(session_id, task_data)
    
    assert len(session.task_history) == 1
    assert session.task_history[0]["data"] == task_data
    assert "timestamp" in session.task_history[0]

@pytest.mark.asyncio
async def test_websocket_connection_and_disconnect():
    """測試 WebSocket 連線與中斷"""
    manager = SessionManager()
    session_id = manager.create_session()
    
    # 建立 Mock WebSocket
    mock_ws = AsyncMock()
    
    # 1. 連接 WebSocket
    connected = await manager.connect_websocket(session_id, mock_ws)
    assert connected is True
    
    session = manager.get_session(session_id)
    assert session.websocket is mock_ws
    assert session.is_connected is True
    # 驗證 websocket.accept() 有被呼叫
    mock_ws.accept.assert_called_once()

    # 2. 中斷連線
    manager.disconnect_websocket(session_id)
    assert session.websocket is None
    assert session.is_connected is False

    # 測試對不存在的會話連接，應該回傳 False
    assert await manager.connect_websocket("invalid-id", mock_ws) is False

@pytest.mark.asyncio
async def test_send_message_via_websocket():
    """測試透過 WebSocket 發送訊息"""
    manager = SessionManager()
    session_id = manager.create_session()
    mock_ws = AsyncMock()
    
    # 1. 在未連接狀態下發送，應回傳 False
    assert await manager.send_message(session_id, {"msg": "hello"}) is False

    # 2. 連接後發送，應回傳 True 且呼叫 send_json
    await manager.connect_websocket(session_id, mock_ws)
    success = await manager.send_message(session_id, {"msg": "test"})
    assert success is True
    mock_ws.send_json.assert_called_with({"msg": "test"})

    # 3. 發送時若拋出 Exception，應回傳 False 且標記 disconnected
    mock_ws.send_json.side_effect = RuntimeError("Connection closed")
    success_fail = await manager.send_message(session_id, {"msg": "broken"})
    assert success_fail is False
    assert manager.get_session(session_id).is_connected is False

def test_cleanup_expired_sessions():
    """測試清理過期會話的功能"""
    manager = SessionManager()
    
    # 建立兩個會話
    sid_active = manager.create_session()
    sid_expired = manager.create_session()
    
    # 取得會話實例
    session_active = manager.get_session(sid_active)
    session_expired = manager.get_session(sid_expired)
    
    # 將 session_expired 的最後活動時間設為 2 小時前 (超時)
    session_expired.last_active = datetime.now() - timedelta(hours=2)
    # 保持 active_session 為最近活動
    session_active.last_active = datetime.now()
    
    assert manager.get_active_sessions_count() == 2
    
    # 執行清理
    manager.cleanup_expired_sessions()
    
    # 驗證過期會話已被刪除，活躍會話仍保留
    assert manager.get_active_sessions_count() == 1
    assert sid_active in manager._sessions
    assert sid_expired not in manager._sessions
