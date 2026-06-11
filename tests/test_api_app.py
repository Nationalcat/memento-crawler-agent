import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect
from models import TaskStatus, AgentState
from api.session import SessionManager
from api.app import app, WebSocketObserver

# Reset session manager singleton before and after each test
@pytest.fixture(autouse=True)
def clean_sessions():
    SessionManager.reset()
    yield
    SessionManager.reset()

def test_root_endpoint():
    """測試首頁 GET /"""
    client = TestClient(app)
    # 建立一個臨時 Mock open 避免實體讀寫，或使用實體靜態網頁
    with patch("builtins.open", mock_open=True) as mock_file:
        mock_file.return_value.__enter__.return_value.read.return_value = "<html>index</html>"
        response = client.get("/")
        assert response.status_code == 200
        assert "index" in response.text

def test_create_session():
    """測試建立會話 POST /api/session/create"""
    client = TestClient(app)
    response = client.post("/api/session/create")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["message"] == "會話建立成功"

def test_get_session_status():
    """測試查詢會話狀態 GET /api/session/{session_id}/status"""
    client = TestClient(app)
    
    # 1. 查詢不存在的會話
    response = client.get("/api/session/non-existent/status")
    assert response.status_code == 200
    assert response.json() == {"error": "會話不存在"}

    # 2. 查詢存在的會話
    create_res = client.post("/api/session/create")
    session_id = create_res.json()["session_id"]
    
    status_res = client.get(f"/api/session/{session_id}/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["session_id"] == session_id
    assert status_data["is_connected"] is False
    assert status_data["task_history_count"] == 0

def test_get_stats():
    """測試系統統計 GET /api/stats"""
    client = TestClient(app)
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "active_sessions" in data
    assert "server_time" in data

def test_websocket_observer_status_update():
    """測試 WebSocketObserver.update 的正常推送與 metadata 處理"""
    manager = SessionManager()
    session_id = manager.create_session()
    
    # 建立 Mock websocket
    mock_ws = AsyncMock()
    # 綁定 websocket
    manager._sessions[session_id].websocket = mock_ws
    manager._sessions[session_id].is_connected = True
    
    observer = WebSocketObserver(session_id)
    
    # 測試正常更新
    state = {
        "status": TaskStatus.EXECUTING,
        "task_id": "task_1",
        "current_step": 3,
        "total_steps": 10,
        "extracted_data": [{}],
        "error_log": ["error"],
        "metadata": {
            "retry_progress": "retrying..."
        }
    }
    
    # 執行 update 觀察者方法
    asyncio.run(observer.update(state))
    
    # 驗證是否呼叫 send_json (即 websocket.send_json)
    mock_ws.send_json.assert_called()
    msg = mock_ws.send_json.call_args[0][0]
    assert msg["type"] == "status_update"
    assert msg["status"] == "executing"
    assert msg["retry_progress"] == "retrying..."

def test_websocket_observer_rejected_status():
    """測試 WebSocketObserver 處理 TaskStatus.REJECTED 時推送拒絕訊息"""
    manager = SessionManager()
    session_id = manager.create_session()
    
    mock_ws = AsyncMock()
    manager._sessions[session_id].websocket = mock_ws
    manager._sessions[session_id].is_connected = True
    
    observer = WebSocketObserver(session_id)
    
    state = {
        "status": TaskStatus.REJECTED,
        "reject_reason": "url_empty",
        "error_log": ["URL is empty"],
        "metadata": {
            "status_code": 400
        }
    }
    
    asyncio.run(observer.update(state))
    
    # 驗證發送了 reject_task 訊息
    # 呼叫了兩次：第一次 status_update, 第二次 reject_task
    assert mock_ws.send_json.call_count == 2
    args_list = [call[0][0] for call in mock_ws.send_json.call_args_list]
    reject_msg = args_list[1]
    assert reject_msg["type"] == "reject_task"
    assert reject_msg["reason"] == "url_empty"
    assert reject_msg["message"] == "URL is empty"
    assert reject_msg["status_code"] == 400

@pytest.mark.asyncio
async def test_websocket_observer_update_sync():
    """測試 WebSocketObserver.update_sync 同步執行方法"""
    observer = WebSocketObserver("sid")
    # Mock update
    observer.update = AsyncMock()
    
    state = {"status": "pending"}
    observer.update_sync(state)
    # 給它一點時間運行 create_task
    await asyncio.sleep(0.01)
    observer.update.assert_called_with(state)

def test_websocket_endpoints_errors():
    """測試 WebSocket 端點異常連線 (會話不存在 / 連線失敗)"""
    client = TestClient(app)
    
    # 1. 會話不存在 (4000)
    with pytest.raises(Exception):
        client.websocket_connect("/ws/invalid-session").__enter__()

    # 2. 連線失敗 (4001)
    create_res = client.post("/api/session/create")
    session_id = create_res.json()["session_id"]
    
    # 模擬 connect_websocket 失敗
    with patch.object(SessionManager, "connect_websocket", return_value=False):
        with pytest.raises(Exception):
            client.websocket_connect(f"/ws/{session_id}").__enter__()

def test_websocket_messaging_flow():
    """測試 WebSocket 正確處理 ping、cancel_task 與 start_task"""
    client = TestClient(app)
    
    # 建立會話
    create_res = client.post("/api/session/create")
    session_id = create_res.json()["session_id"]
    
    # 建立連線
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        # 1. 驗證連線成功訊息
        conn_msg = websocket.receive_json()
        assert conn_msg["type"] == "connected"
        
        # 2. 測試 ping -> pong
        websocket.send_json({"type": "ping"})
        pong_msg = websocket.receive_json()
        assert pong_msg["type"] == "pong"
        
        # 3. 測試 cancel_task -> task_cancelled
        websocket.send_json({"type": "cancel_task"})
        cancel_msg = websocket.receive_json()
        assert cancel_msg["type"] == "task_cancelled"
        assert "已取消" in cancel_msg["message"]

        # 4. 測試 start_task 缺少參數
        websocket.send_json({"type": "start_task"})
        err_msg = websocket.receive_json()
        assert err_msg["type"] == "error"
        assert "缺少必要參數" in err_msg["message"]

        # 5. 測試 start_task 正常運作 (包含 workflow.run 與完成推播)
        with patch("api.app.CrawlerWorkflow") as MockWorkflow:
            mock_flow = MagicMock()
            # 模擬正常執行狀態
            mock_flow.run = AsyncMock(return_value={
                "task_id": "task_1",
                "status": TaskStatus.COMPLETED,
                "extracted_data": [{"name": "A"}],
                "error_log": [],
                "retry_count": 1,
                "metadata": {
                    "skill_action": "created",
                    "skill_id": "skill_1"
                }
            })
            MockWorkflow.return_value = mock_flow
            
            websocket.send_json({
                "type": "start_task",
                "url": "http://example.com",
                "instruction": "get items"
            })
            
            # 第一個訊息：伺服器響應 task_started
            msg1 = websocket.receive_json()
            assert msg1["type"] == "task_started"
            
            # 第二個訊息：由 handle_start_task 完成後的 task_completed 推送
            msg2 = websocket.receive_json()
            assert msg2["type"] == "task_completed"
            assert msg2["extracted_data"] == [{"name": "A"}]
            assert msg2["retry_count"] == 1
            assert msg2["skill_id"] == "skill_1"

        # 6. 測試 retry_with_new_url 正常運作 (包含 workflow 拋出 Exception)
        with patch("api.app.CrawlerWorkflow") as MockWorkflow:
            mock_flow = MagicMock()
            mock_flow.run = AsyncMock(side_effect=RuntimeError("Workflow run crash"))
            MockWorkflow.return_value = mock_flow
            
            websocket.send_json({
                "type": "retry_with_new_url",
                "url": "http://example.com",
                "instruction": "get items"
            })
            
            msg_started = websocket.receive_json()
            assert msg_started["type"] == "task_started"
            
            msg_err = websocket.receive_json()
            assert msg_err["type"] == "task_error"
            assert "Workflow run crash" in msg_err["message"]

def test_websocket_disconnect_and_exceptions():
    """測試 WebSocketDisconnect 中斷以及其他異常情況下的 WebSocket 關閉"""
    client = TestClient(app)
    create_res = client.post("/api/session/create")
    session_id = create_res.json()["session_id"]
    
    # 1. 測試 WebSocketDisconnect 正常中斷並呼叫 disconnect_websocket
    with patch("fastapi.WebSocket.receive_json", new_callable=AsyncMock) as mock_receive:
        mock_receive.side_effect = WebSocketDisconnect(code=1000)
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
        
        session = SessionManager().get_session(session_id)
        assert session.is_connected is False

    # 2. 測試其他 Exception 異常處理，伺服器會發送 type="error" 訊息並斷開連線
    create_res2 = client.post("/api/session/create")
    session_id2 = create_res2.json()["session_id"]
    with patch("fastapi.WebSocket.receive_json", new_callable=AsyncMock) as mock_receive2:
        mock_receive2.side_effect = RuntimeError("Socket read error")
        with client.websocket_connect(f"/ws/{session_id2}") as websocket2:
            data = websocket2.receive_json()
            assert data["type"] == "connected"
            err_data = websocket2.receive_json()
            assert err_data["type"] == "error"
            assert "Socket read error" in err_data["message"]
        
        session2 = SessionManager().get_session(session_id2)
        assert session2.is_connected is False

