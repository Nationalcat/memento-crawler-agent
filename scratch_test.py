import asyncio
from graph import CrawlerWorkflow
from observers import TaskMonitor, ConsoleLogger
from skills.memory import SkillMemory

async def main():
    # 註解清理以測試讀取已存技能的執行結果
    # memory = SkillMemory()
    # for skill_id in list(memory._community_skills.keys()):
    #     memory.delete_skill(skill_id)
    # memory.reset()
    
    monitor = TaskMonitor()
    monitor.attach(ConsoleLogger())
    
    workflow = CrawlerWorkflow()
    result = await workflow.run(
        url="https://www.meimaii.com",
        instruction="給我十個商品名稱"
    )
    print("\n=== Test Run Result ===")
    print("Result status:", result["status"])
    print("Extracted Data:", result.get("extracted_data"))
    print("Error log:", result["error_log"])

if __name__ == "__main__":
    asyncio.run(main())
