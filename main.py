"""
主程式入口
支援兩種啟動模式：
1. CLI 模式：直接執行爬蟲任務
2. Web 模式：啟動 FastAPI 伺服器
"""
import asyncio
import sys
from graph import CrawlerWorkflow
from observers import TaskMonitor, ConsoleLogger, ErrorAlert


async def run_cli():
    """
    CLI 模式執行
    直接執行爬蟲任務並輸出結果
    """
    # 初始化任務監控器
    monitor = TaskMonitor()

    # 附加觀察者：控制台日誌與錯誤告警
    monitor.attach(ConsoleLogger())
    monitor.attach(ErrorAlert())

    # 建立爬蟲工作流
    workflow = CrawlerWorkflow()

    # 執行爬蟲任務
    result = await workflow.run(
        url="https://www.example-ecommerce.com/products",
        instruction="抓取所有商品名稱、價格和評價"
    )

    # 輸出執行結果
    print("\n=== 任務執行結果 ===")
    print(f"任務 ID: {result['task_id']}")
    print(f"狀態: {result['status']}")
    print(f"提取資料數量: {len(result['extracted_data'])}")
    print(f"重試次數: {result['retry_count']}")

    # 若有錯誤記錄則輸出
    if result['error_log']:
        print("\n錯誤記錄:")
        for error in result['error_log']:
            print(f"  - {error}")


def run_web():
    """
    Web 模式執行
    啟動 FastAPI 伺服器
    """
    import uvicorn
    print("啟動 Memento-Skills 爬蟲 Agent Web 伺服器...")
    print("訪問 http://localhost:8000 開始使用")
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    # 根據命令列參數選擇啟動模式
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        asyncio.run(run_cli())
    else:
        run_web()
