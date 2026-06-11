import pytest
from config import settings

# Override database URL to use in-memory SQLite for testing
settings.DATABASE_URL = "sqlite:///:memory:"

from database.connection import Base, engine, SessionLocal
from database.models import DBSkill
from skills.models import CommunitySkill, TargetConfig, Parameter, ExecutionConfig, Extractor, OutputConfig
from skills.memory import SkillMemory


@pytest.fixture(autouse=True)
def setup_db():
    # Create tables in the in-memory database
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)
    # Reset SkillMemory singleton
    SkillMemory.reset()


def test_database_connection():
    db = SessionLocal()
    assert db is not None
    db.close()


def test_db_skill_serialization():
    # Create a dummy Pydantic CommunitySkill
    skill = CommunitySkill(
        id="test_skill_db",
        name="Test DB Skill",
        version="1.0.0",
        author="test-suite",
        description="A skill for testing database persistence",
        tags=["test", "database"],
        target=TargetConfig(domain="test.com", url_patterns=["test.com/*"]),
        parameters=[
            Parameter(name="param1", type="string", required=True, default="val1", description="desc1")
        ],
        execution=ExecutionConfig(wait_time=3, scroll=True),
        extractors=[
            Extractor(name="title", selector="h1", type="text")
        ],
        output=OutputConfig(format="json"),
        prompt="Test prompt template"
    )

    # Convert to DB model
    db_skill = DBSkill.from_pydantic(skill)
    assert db_skill.id == "test_skill_db"
    assert db_skill.name == "Test DB Skill"
    assert "test" in db_skill.tags
    assert "test.com" in db_skill.target

    # Convert back to Pydantic
    pydantic_skill = db_skill.to_pydantic()
    assert pydantic_skill.id == skill.id
    assert pydantic_skill.name == skill.name
    assert pydantic_skill.tags == skill.tags
    assert pydantic_skill.target.domain == skill.target.domain
    assert len(pydantic_skill.parameters) == 1
    assert pydantic_skill.parameters[0].name == "param1"
    assert pydantic_skill.execution.wait_time == 3
    assert pydantic_skill.extractors[0].name == "title"
    assert pydantic_skill.output.format == "json"
    assert pydantic_skill.prompt == "Test prompt template"


def test_skill_memory_db_persistence():
    memory = SkillMemory()
    
    # Create a skill
    skill = CommunitySkill(
        id="mem_skill_db",
        name="Memory DB Skill",
        version="1.0.0",
        author="test-suite",
        description="Testing SkillMemory storage",
        target=TargetConfig(domain="mem.com", url_patterns=["mem.com/*"]),
        prompt="Memory prompt template"
    )

    # Store skill
    memory.store_community_skill(skill)

    # Verify stored in memory
    assert "mem_skill_db" in memory._community_skills

    # Verify stored in DB by querying directly
    db = SessionLocal()
    db_skill = db.query(DBSkill).filter(DBSkill.id == "mem_skill_db").first()
    assert db_skill is not None
    assert db_skill.name == "Memory DB Skill"
    db.close()

    # Reset memory and reload
    SkillMemory.reset()
    new_memory = SkillMemory()
    # Verify it reloads from DB
    assert "mem_skill_db" in new_memory._community_skills
    loaded_skill = new_memory._community_skills["mem_skill_db"]
    assert loaded_skill.name == "Memory DB Skill"

    # Update skill
    loaded_skill.description = "Updated description"
    new_memory.update_community_skill(loaded_skill)

    # Verify updated in DB
    db = SessionLocal()
    db_skill = db.query(DBSkill).filter(DBSkill.id == "mem_skill_db").first()
    assert db_skill.description == "Updated description"
    # Check that version was incremented (1.0.0 -> 1.0.1)
    assert db_skill.version == "1.0.1"
    db.close()

    # Delete skill
    success = new_memory.delete_skill("mem_skill_db")
    assert success is True

    # Verify deleted from memory and DB
    assert "mem_skill_db" not in new_memory._community_skills
    db = SessionLocal()
    db_skill = db.query(DBSkill).filter(DBSkill.id == "mem_skill_db").first()
    assert db_skill is None
    db.close()


def test_crawl_result_persistence():
    db = SessionLocal()
    from database.models import DBCrawlResult
    
    # Verify table starts empty
    results = db.query(DBCrawlResult).all()
    assert len(results) == 0
    
    # Insert a dummy record
    record = DBCrawlResult(
        task_id="test_task_123",
        url="https://example.com",
        instruction="Get all links",
        extracted_data='[{"link": "https://example.com/1"}]'
    )
    db.add(record)
    db.commit()
    
    # Query it back
    fetched = db.query(DBCrawlResult).filter(DBCrawlResult.task_id == "test_task_123").first()
    assert fetched is not None
    assert fetched.url == "https://example.com"
    assert fetched.instruction == "Get all links"
    assert "example.com/1" in fetched.extracted_data
    db.close()


@pytest.mark.asyncio
async def test_output_result_node_saves_to_db():
    from graph.nodes.output import output_result
    from models import TaskStatus
    import json
    
    state = {
        "task_id": "task_node_test",
        "url": "https://example.com/products",
        "instruction": "extract price",
        "status": TaskStatus.EXECUTING,
        "extracted_data": [{"price": "$100"}],
        "error_log": [],
        "end_time": None
    }
    
    # Run the output node
    updated_state = await output_result(state)
    
    # Verify node behavior
    assert updated_state["status"] == TaskStatus.COMPLETED
    assert updated_state["end_time"] is not None
    
    # Verify saved in the DB
    from database.models import DBCrawlResult
    db = SessionLocal()
    saved = db.query(DBCrawlResult).filter(DBCrawlResult.task_id == "task_node_test").first()
    assert saved is not None
    assert saved.url == "https://example.com/products"
    assert saved.instruction == "extract price"
    data = json.loads(saved.extracted_data)
    assert data == [{"price": "$100"}]
    db.close()
