"""
FastAPI 啟動腳本
啟動 Web 伺服器並提供 API 與 WebSocket 服務
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
