import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from models import AgentState, TaskStatus
from agents import AgentFactory, AgentType

# Import the node functions
from graph.nodes.validation import validate_input, check_url_access, reject_task
from graph.nodes.skill import retrieve_skill, update_skill
from graph.nodes.output import output_result
from graph.nodes.execution import execute_with_skill, execute_auto, handle_error, parse_data


@pytest.fixture
def base_state() -> AgentState:
    return {
        "task_id": "test-task-123",
        "url": "example.com",
        "instruction": "get titles",
        "status": TaskStatus.PENDING,
        "current_step": 0,
        "total_steps": 10,
        "extracted_data": [],
        "error_log": [],
        "skill_id": None,
        "use_skill": False,
        "skill_failed": False,
        "execution_source": "none",
        "skill_object": None,
        "retry_count": 0,
        "start_time": datetime.now(),
        "end_time": None,
        "metadata": {},
        "current_strategy": None,
        "original_strategy": None,
        "reject_reason": None
    }


@pytest.mark.asyncio
async def test_validation_nodes(base_state):
    # Mock Harness Agent
    mock_harness = MagicMock()
    mock_harness.validate_input = AsyncMock(return_value=base_state)
    mock_harness.check_url_access = AsyncMock(return_value=base_state)
    mock_harness.reject_task = AsyncMock(return_value=base_state)

    with patch.object(AgentFactory, "create", return_value=mock_harness) as mock_create:
        # Test validate_input node
        res = await validate_input(base_state)
        mock_create.assert_any_call(AgentType.HARNESS, "harness_main")
        mock_harness.validate_input.assert_awaited_once_with(base_state)
        assert res == base_state

        # Test check_url_access node
        res_url = await check_url_access(base_state)
        mock_harness.check_url_access.assert_awaited_once_with(base_state)
        assert res_url == base_state

        # Test reject_task node
        res_reject = await reject_task(base_state)
        mock_harness.reject_task.assert_awaited_once_with(base_state)
        assert res_reject == base_state


@pytest.mark.asyncio
async def test_skill_nodes(base_state):
    # Mock Harness Agent
    mock_harness = MagicMock()
    mock_harness.retrieve_skill = AsyncMock(return_value=base_state)
    mock_harness.update_skill_library = AsyncMock(return_value=base_state)

    with patch.object(AgentFactory, "create", return_value=mock_harness) as mock_create:
        # Test retrieve_skill node
        res = await retrieve_skill(base_state)
        mock_create.assert_any_call(AgentType.HARNESS, "harness_main")
        mock_harness.retrieve_skill.assert_awaited_once_with(base_state)
        assert res == base_state

        # Test update_skill node
        res_update = await update_skill(base_state)
        mock_harness.update_skill_library.assert_awaited_once_with(base_state)
        assert res_update == base_state


@pytest.mark.asyncio
async def test_output_result_node(base_state):
    # If not in failed or rejected status, it should set status to completed
    res = await output_result(base_state)
    assert res["status"] == TaskStatus.COMPLETED
    assert isinstance(res["end_time"], datetime)

    # If already failed, status is unchanged
    failed_state = base_state.copy()
    failed_state["status"] = TaskStatus.FAILED
    res_failed = await output_result(failed_state)
    assert res_failed["status"] == TaskStatus.FAILED

    # If already rejected, status is unchanged
    rejected_state = base_state.copy()
    rejected_state["status"] = TaskStatus.REJECTED
    res_rejected = await output_result(rejected_state)
    assert res_rejected["status"] == TaskStatus.REJECTED


@pytest.mark.asyncio
async def test_execution_nodes(base_state):
    # Mock Executor and Harness Agent
    mock_executor = MagicMock()
    mock_executor.execute_with_skill = AsyncMock(return_value=base_state)
    mock_executor.execute_auto = AsyncMock(return_value=base_state)

    mock_harness = MagicMock()
    mock_harness.handle_error_with_llm = AsyncMock(return_value=base_state)

    def side_effect(agent_type, name):
        if agent_type == AgentType.EXECUTOR:
            return mock_executor
        return mock_harness

    with patch.object(AgentFactory, "create", side_effect=side_effect) as mock_create:
        # Test execute_with_skill node
        res_skill = await execute_with_skill(base_state)
        mock_executor.execute_with_skill.assert_awaited_once_with(base_state)
        assert res_skill == base_state

        # Test execute_auto node
        res_auto = await execute_auto(base_state)
        mock_executor.execute_auto.assert_awaited_once_with(base_state)
        assert res_auto == base_state

        # Test handle_error node
        res_err = await handle_error(base_state)
        mock_harness.handle_error_with_llm.assert_awaited_once_with(base_state)
        assert res_err == base_state


@pytest.mark.asyncio
async def test_parse_data_node(base_state):
    # Case 1: No extracted_data -> returns state as-is, status set to EXTRACTING
    res = await parse_data(base_state)
    assert res["status"] == TaskStatus.EXTRACTING
    assert res["extracted_data"] == []

    # Case 2: Has extracted_data, clean_data returns a list
    state_with_data = base_state.copy()
    state_with_data["extracted_data"] = [{"title": "   dirty text  "}]
    
    mock_cleaned_list = [{"title": "dirty text"}]
    with patch("utils.llm_manager.clean_data", AsyncMock(return_value=mock_cleaned_list)) as mock_clean:
        res_list = await parse_data(state_with_data)
        mock_clean.assert_awaited_once()
        assert res_list["extracted_data"] == mock_cleaned_list

    # Case 3: Has extracted_data, clean_data returns dict containing "data" key
    state_with_data = base_state.copy()
    state_with_data["extracted_data"] = [{"title": "dirty"}]
    mock_cleaned_dict = {"data": [{"title": "cleaned"}]}
    with patch("utils.llm_manager.clean_data", AsyncMock(return_value=mock_cleaned_dict)):
        res_dict = await parse_data(state_with_data)
        assert res_dict["extracted_data"] == [{"title": "cleaned"}]

    # Case 4: Has extracted_data, clean_data returns something else (fallback to original)
    state_with_data = base_state.copy()
    state_with_data["extracted_data"] = [{"title": "dirty"}]
    with patch("utils.llm_manager.clean_data", AsyncMock(return_value="unexpected string")):
        res_other = await parse_data(state_with_data)
        assert res_other["extracted_data"] == [{"title": "dirty"}]

    # Case 5: clean_data raises an exception (fallback + warn)
    state_with_data = base_state.copy()
    state_with_data["extracted_data"] = [{"title": "dirty"}]
    state_with_data["error_log"] = []
    with patch("utils.llm_manager.clean_data", AsyncMock(side_effect=Exception("llm failed"))):
        res_ex = await parse_data(state_with_data)
        assert res_ex["extracted_data"] == [{"title": "dirty"}]
        assert len(res_ex["error_log"]) == 1
        assert "llm failed" in res_ex["error_log"][0]
