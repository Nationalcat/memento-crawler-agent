import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from models import TaskStatus
from config import settings
from graph.workflow import CrawlerWorkflow


def test_workflow_init():
    with patch("graph.workflow.StateGraph") as mock_state_graph:
        mock_compiled = MagicMock()
        mock_state_graph.return_value.compile.return_value = mock_compiled
        
        workflow = CrawlerWorkflow()
        assert workflow.graph is mock_compiled
        mock_state_graph.return_value.compile.assert_called_once()


def test_conditional_edges():
    workflow = CrawlerWorkflow()

    # Test _check_validation
    state_pass = {"status": TaskStatus.PENDING}
    state_fail = {"status": TaskStatus.REJECTED}
    assert workflow._check_validation(state_pass) == "pass"
    assert workflow._check_validation(state_fail) == "fail"

    # Test _check_accessibility
    assert workflow._check_accessibility(state_pass) == "accessible"
    assert workflow._check_accessibility(state_fail) == "inaccessible"

    # Test _has_skill
    state_has_skill = {"use_skill": True, "skill_object": {"id": "1"}}
    state_no_skill_1 = {"use_skill": False, "skill_object": {"id": "1"}}
    state_no_skill_2 = {"use_skill": True, "skill_object": None}
    assert workflow._has_skill(state_has_skill) == "has_skill"
    assert workflow._has_skill(state_no_skill_1) == "no_skill"
    assert workflow._has_skill(state_no_skill_2) == "no_skill"

    # Test _check_execution
    state_success = {"status": TaskStatus.COMPLETED}
    state_failed = {"status": TaskStatus.FAILED}
    assert workflow._check_execution(state_success) == "success"
    assert workflow._check_execution(state_failed) == "fail"

    # Test _should_retry
    state_retry = {"retry_count": settings.MAX_RETRY_COUNT - 1}
    state_exceed = {"retry_count": settings.MAX_RETRY_COUNT}
    assert workflow._should_retry(state_retry) == "retry"
    assert workflow._should_retry(state_exceed) == "exceed"


@pytest.mark.asyncio
async def test_workflow_run():
    workflow = CrawlerWorkflow()
    mock_ainvoke = AsyncMock(return_value={"status": "done"})
    workflow.graph.ainvoke = mock_ainvoke

    res = await workflow.run(url="example.com", instruction="test instruction")
    assert res == {"status": "done"}
    
    # Verify the initial state passed to ainvoke
    mock_ainvoke.assert_called_once()
    initial_state = mock_ainvoke.call_args[0][0]
    assert initial_state["url"] == "example.com"
    assert initial_state["instruction"] == "test instruction"
    assert initial_state["status"] == TaskStatus.PENDING
    assert initial_state["retry_count"] == 0
    assert initial_state["use_skill"] is False
    assert initial_state["extracted_data"] == []
