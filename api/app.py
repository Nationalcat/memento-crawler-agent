"""
FastAPI 應用模組
提供 REST API 與 WebSocket 端點
實現會話管理、任務執行與即時狀態推送
支援任務拒絕、重試進度推送等功能
"""
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from datetime import datetime

from .session import SessionManager
from graph import CrawlerWorkflow
from observers import TaskMonitor, Observer
from models import AgentState, TaskStatus


# 建立 FastAPI 應用
app = FastAPI(
    title="Memento-Skills 爬蟲 Agent API",
    description="具備自主學習能力的電商爬蟲系統",
    version="1.1.0"
)

# 掛載靜態檔案
app.mount("/static", StaticFiles(directory="static"), name="static")

# 初始化會話管理器
session_manager = SessionManager()


class WebSocketObserver(Observer):
    """
    WebSocket 觀察者
    將任務狀態變更透過 WebSocket 推送給前端
    """

    def __init__(self, session_id: str):
        """
        初始化
        參數:
            session_id: 關聯的會話 ID
        """
        self.session_id = session_id

    async def update(self, state: AgentState) -> None:
        """
        接收狀態更新並透過 WebSocket 推送
        參數:
            state: 當前 Agent 狀態
        """
        status = state.get("status")
        status_value = status.value if isinstance(status, TaskStatus) else status

        message = {
            "type": "status_update",
            "task_id": state.get("task_id"),
            "status": status_value,
            "current_step": state.get("current_step"),
            "total_steps": state.get("total_steps"),
            "extracted_data_count": len(state.get("extracted_data", [])),
            "error_count": len(state.get("error_log", [])),
            "timestamp": datetime.now().isoformat()
        }

        # 推送重試進度
        retry_progress = state.get("metadata", {}).get("retry_progress")
        if retry_progress:
            message["retry_progress"] = retry_progress

        await session_manager.send_message(self.session_id, message)

        # 如果任務被拒絕，發送拒絕訊息
        if status == TaskStatus.REJECTED:
            await self._send_reject_message(state)

    async def _send_reject_message(self, state: AgentState) -> None:
        """
        發送任務拒絕訊息
        參數:
            state: 當前 Agent 狀態
        """
        reject_reason = state.get("reject_reason", "unknown")
        error_log = state.get("error_log", [])
        error_message = error_log[-1] if error_log else "未知錯誤"

        message = {
            "type": "reject_task",
            "reason": reject_reason,
            "message": error_message,
            "status_code": state.get("metadata", {}).get("status_code"),
            "timestamp": datetime.now().isoformat()
        }

        await session_manager.send_message(self.session_id, message)

    def update_sync(self, state: AgentState) -> None:
        """同步版本的更新（用於非同步環境）"""
        asyncio.create_task(self.update(state))


@app.get("/", response_class=HTMLResponse)
async def root():
    """首頁，返回前端測試頁面"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/session/create")
async def create_session():
    """
    建立新會話
    回傳:
        sessionId: 新建立的會話識別碼
    """
    session_id = session_manager.create_session()
    return {
        "session_id": session_id,
        "message": "會話建立成功"
    }


@app.get("/api/session/{session_id}/status")
async def get_session_status(session_id: str):
    """
    獲取會話狀態
    參數:
        session_id: 會話識別碼
    回傳:
        會話狀態資訊
    """
    session = session_manager.get_session(session_id)
    if not session:
        return {"error": "會話不存在"}

    return {
        "session_id": session.session_id,
        "is_connected": session.is_connected,
        "created_at": session.created_at.isoformat(),
        "last_active": session.last_active.isoformat(),
        "task_history_count": len(session.task_history),
        "current_state": session.current_state
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket 端點
    建立即時通訊通道，用於：
    1. 接收前端任務指令
    2. 推送任務執行狀態
    3. 推送錯誤告警
    4. 推送任務拒絕訊息
    5. 推送重試進度
    參數:
        websocket: WebSocket 實例
        session_id: 會話識別碼
    """
    # 檢查會話是否存在
    session = session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=4000, reason="會話不存在")
        return

    # 連接 WebSocket
    connected = await session_manager.connect_websocket(session_id, websocket)
    if not connected:
        await websocket.close(code=4001, reason="連接失敗")
        return

    try:
        # 發送連接成功訊息
        await session_manager.send_message(session_id, {
            "type": "connected",
            "message": "WebSocket 連接成功",
            "session_id": session_id
        })

        # 監聽前端訊息
        while True:
            data = await websocket.receive_json()

            # 處理不同類型的訊息
            if data.get("type") == "start_task":
                # 啟動爬蟲任務
                await handle_start_task(session_id, data)

            elif data.get("type") == "cancel_task":
                # 取消任務
                await handle_cancel_task(session_id)

            elif data.get("type") == "retry_with_new_url":
                # 使用新 URL 重試
                await handle_start_task(session_id, data)

            elif data.get("type") == "ping":
                # 心跳檢測
                await session_manager.send_message(session_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        # 連線斷開
        session_manager.disconnect_websocket(session_id)
        print(f"會話 {session_id} 的 WebSocket 已斷開")

    except Exception as e:
        # 發生錯誤
        await session_manager.send_message(session_id, {
            "type": "error",
            "message": str(e)
        })
        session_manager.disconnect_websocket(session_id)


async def handle_start_task(session_id: str, data: Dict[str, Any]):
    """
    處理啟動任務請求
    參數:
        session_id: 會話識別碼
        data: 任務資料（包含 url 和 instruction）
    """
    url = data.get("url")
    instruction = data.get("instruction")

    if not url or not instruction:
        await session_manager.send_message(session_id, {
            "type": "error",
            "message": "缺少必要參數：url 或 instruction"
        })
        return

    # 發送任務啟動訊息
    await session_manager.send_message(session_id, {
        "type": "task_started",
        "message": "任務開始執行",
        "url": url,
        "instruction": instruction
    })

    # 建立工作流並執行
    workflow = CrawlerWorkflow()

    # 建立 WebSocket 觀察者並訂閱
    ws_observer = WebSocketObserver(session_id)
    monitor = TaskMonitor()
    monitor.attach(ws_observer)

    try:
        # 執行工作流
        result = await workflow.run(url, instruction)

        # 更新會話狀態
        status = result.get("status")
        status_value = status.value if isinstance(status, TaskStatus) else status

        session_manager.update_session_state(session_id, {
            "task_id": result.get("task_id"),
            "status": status_value,
            "extracted_data": result.get("extracted_data"),
            "error_log": result.get("error_log")
        })

        # 將任務加入歷史
        session_manager.add_task_to_history(session_id, {
            "task_id": result.get("task_id"),
            "url": url,
            "status": status_value
        })

        # 發送完成訊息（如果不是拒絕狀態）
        if status != TaskStatus.REJECTED:
            skill_action = result.get("metadata", {}).get("skill_action", "none")
            skill_id = result.get("metadata", {}).get("skill_id")

            await session_manager.send_message(session_id, {
                "type": "task_completed",
                "task_id": result.get("task_id"),
                "status": status_value,
                "extracted_data": result.get("extracted_data"),
                "error_log": result.get("error_log"),
                "retry_count": result.get("retry_count"),
                "skill_action": skill_action,
                "skill_id": skill_id
            })

    except Exception as e:
        # 發送錯誤訊息
        await session_manager.send_message(session_id, {
            "type": "task_error",
            "message": str(e)
        })

    finally:
        # 分離觀察者
        monitor.detach(ws_observer)


async def handle_cancel_task(session_id: str):
    """
    處理取消任務請求
    參數:
        session_id: 會話識別碼
    """
    await session_manager.send_message(session_id, {
        "type": "task_cancelled",
        "message": "任務已取消"
    })


@app.get("/api/stats")
async def get_stats():
    """獲取系統統計資訊"""
    return {
        "active_sessions": session_manager.get_active_sessions_count(),
        "server_time": datetime.now().isoformat()
    }
