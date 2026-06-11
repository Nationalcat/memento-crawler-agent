"""
輸出節點模組
負責最終結果輸出
"""
from models import AgentState, TaskStatus
from agents import AgentFactory, AgentType
from datetime import datetime


async def output_result(state: AgentState) -> AgentState:
    """
    輸出結果節點
    - 設置結束時間
    - 確保狀態正確
    - 儲存爬取成功的結果到資料庫中
    
    參數:
        state: 當前 Agent 狀態
    回傳:
        更新後的 Agent 狀態
    """
    state['current_step'] = 10
    if state['status'] not in [TaskStatus.FAILED, TaskStatus.REJECTED]:
        state['status'] = TaskStatus.COMPLETED

        # 儲存爬取成功的結果到資料庫中
        if state.get('extracted_data'):
            try:
                import json
                from database.connection import SessionLocal
                from database.models import DBCrawlResult

                db = SessionLocal()
                try:
                    # 避免重複寫入相同 task_id 的結果
                    existing = db.query(DBCrawlResult).filter(DBCrawlResult.task_id == state['task_id']).first()
                    if not existing:
                        serialized_data = json.dumps(state['extracted_data'], ensure_ascii=False)
                        crawl_result = DBCrawlResult(
                            task_id=state['task_id'],
                            url=state['url'],
                            instruction=state['instruction'],
                            extracted_data=serialized_data
                        )
                        db.add(crawl_result)
                        db.commit()
                finally:
                    db.close()
            except Exception as e:
                # 寫入失敗僅記錄錯誤日誌，不影響工作流完成
                state['error_log'].append(f"[資料庫寫入錯誤] 儲存提取結果失敗: {str(e)}")

    state['end_time'] = datetime.now()
    from observers import TaskMonitor
    monitor = TaskMonitor()
    monitor.update_state(state)
    return state
