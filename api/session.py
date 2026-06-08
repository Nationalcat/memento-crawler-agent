"""
會話管理器模組
使用 sessionId 管理臨時記憶與 WebSocket 連線
實現無帳號狀態下的任務狀態追蹤
"""
import uuid
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from fastapi import WebSocket


@dataclass
class Session:
    """
    會話資料結構
    儲存單次會話的所有狀態資訊
    """
    session_id: str                          # 會話唯一識別碼
    created_at: datetime = field(default_factory=datetime.now)  # 建立時間
    last_active: datetime = field(default_factory=datetime.now) # 最後活動時間
    websocket: Optional[WebSocket] = None    # WebSocket 連線實例
    task_history: list = field(default_factory=list)            # 任務執行歷史
    current_state: Optional[Dict[str, Any]] = None             # 當前任務狀態
    is_connected: bool = False               # 連線狀態


class SessionManager:
    """
    會話管理器（單例模式）
    管理所有會話的生命週期，提供：
    1. 會話建立與銷毀
    2. WebSocket 連線管理
    3. 臨時記憶儲存
    """
    _instance: Optional['SessionManager'] = None
    _sessions: Dict[str, Session] = {}
    _session_timeout: timedelta = timedelta(hours=1)  # 會話過期時間

    def __new__(cls):
        """單例模式實作"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_session(self) -> str:
        """
        建立新會話
        回傳:
            新建立的 sessionId
        """
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = Session(
            session_id=session_id
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        獲取會話
        參數:
            session_id: 會話識別碼
        回傳:
            會話實例或 None
        """
        session = self._sessions.get(session_id)
        if session:
            # 更新最後活動時間
            session.last_active = datetime.now()
        return session

    def update_session_state(self, session_id: str, state: Dict[str, Any]) -> None:
        """
        更新會話狀態（臨時記憶）
        參數:
            session_id: 會話識別碼
            state: 新的狀態資料
        """
        session = self.get_session(session_id)
        if session:
            session.current_state = state
            session.last_active = datetime.now()

    def add_task_to_history(self, session_id: str, task_data: Dict[str, Any]) -> None:
        """
        將任務加入歷史記錄
        參數:
            session_id: 會話識別碼
            task_data: 任務資料
        """
        session = self.get_session(session_id)
        if session:
            session.task_history.append({
                "timestamp": datetime.now().isoformat(),
                "data": task_data
            })
            session.last_active = datetime.now()

    async def connect_websocket(self, session_id: str, websocket: WebSocket) -> bool:
        """
        連接 WebSocket 到會話
        參數:
            session_id: 會話識別碼
            websocket: WebSocket 實例
        回傳:
            是否連接成功
        """
        session = self.get_session(session_id)
        if session:
            await websocket.accept()
            session.websocket = websocket
            session.is_connected = True
            return True
        return False

    def disconnect_websocket(self, session_id: str) -> None:
        """
        斷開 WebSocket 連線
        參數:
            session_id: 會話識別碼
        """
        session = self.get_session(session_id)
        if session:
            session.websocket = None
            session.is_connected = False

    async def send_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """
        透過 WebSocket 發送訊息
        參數:
            session_id: 會話識別碼
            message: 訊息資料
        回傳:
            是否發送成功
        """
        session = self.get_session(session_id)
        if session and session.websocket and session.is_connected:
            try:
                await session.websocket.send_json(message)
                return True
            except Exception:
                session.is_connected = False
                return False
        return False

    def remove_session(self, session_id: str) -> None:
        """
        移除會話
        參數:
            session_id: 會話識別碼
        """
        if session_id in self._sessions:
            del self._sessions[session_id]

    def cleanup_expired_sessions(self) -> None:
        """清理過期會話"""
        now = datetime.now()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_active > self._session_timeout
        ]
        for sid in expired:
            self.remove_session(sid)

    def get_active_sessions_count(self) -> int:
        """獲取活躍會話數量"""
        return len(self._sessions)

    @classmethod
    def reset(cls) -> None:
        """重置會話管理器（用於測試）"""
        cls._instance = None
        cls._sessions = {}
