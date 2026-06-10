import pytest
from skills.base import BaseSkill

class MockSkill(BaseSkill):
    async def execute(self, state):
        return await super().execute(state)
        
    def validate(self) -> bool:
        return super().validate()

@pytest.mark.asyncio
async def test_base_skill_abc_methods():
    """測試 BaseSkill 的建構式與抽象方法的 pass 定義"""
    skill = MockSkill("test-id", "Test Name")
    
    assert skill.skill_id == "test-id"
    assert skill.name == "Test Name"
    
    # 呼叫基類的 pass 方法以達成 100% 覆蓋率
    assert await skill.execute({}) is None
    assert skill.validate() is None
