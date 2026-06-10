import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from utils.llm import LLMManager, llm_manager
from config import settings


def test_singleton_pattern():
    manager1 = LLMManager()
    manager2 = LLMManager()
    assert manager1 is manager2


def test_init_llm_branches():
    manager = LLMManager()
    
    # 1. API key is empty/None
    with patch.object(settings, "LLM_API_KEY", None):
        manager._init_llm()
        assert manager._llm is None
        
    # 2. API key is set
    with patch.object(settings, "LLM_API_KEY", "mock-key"):
        with patch.object(settings, "LLM_MODEL", "gpt-4o"):
            manager._init_llm()
            assert manager._llm is not None


@pytest.mark.asyncio
async def test_generate_no_llm():
    manager = LLMManager()
    manager._llm = None
    
    with pytest.raises(ValueError, match="LLM 未初始化"):
        await manager.generate("sys", "user")


@pytest.mark.asyncio
async def test_generate_success():
    manager = LLMManager()
    
    # Setup mock ChatOpenAI
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "mock response text"
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    manager._llm = mock_llm
    
    res = await manager.generate("system prompt", "user prompt")
    assert res == "mock response text"
    mock_llm.ainvoke.assert_called_once()
    
    # Check messages passed to ChatOpenAI
    called_messages = mock_llm.ainvoke.call_args[0][0]
    assert len(called_messages) == 2
    assert called_messages[0].content == "system prompt"
    assert called_messages[1].content == "user prompt"


@pytest.mark.asyncio
async def test_generate_json_extraction():
    manager = LLMManager()
    
    # Case 1: Markdown JSON block (```json ... ```)
    with patch.object(manager, "generate", AsyncMock(return_value="```json\n{\"key\": \"val1\"}\n```")):
        res = await manager.generate_json("sys", "user")
        assert res == {"key": "val1"}

    # Case 2: Markdown simple block (``` ... ```)
    with patch.object(manager, "generate", AsyncMock(return_value="```\n{\"key\": \"val2\"}\n```")):
        res = await manager.generate_json("sys", "user")
        assert res == {"key": "val2"}

    # Case 3: Plain string without code blocks
    with patch.object(manager, "generate", AsyncMock(return_value="{\"key\": \"val3\"}")):
        res = await manager.generate_json("sys", "user")
        assert res == {"key": "val3"}

    # Case 4: JSON Decode Error (fallback to raw response dict)
    with patch.object(manager, "generate", AsyncMock(return_value="Not a JSON string")):
        res = await manager.generate_json("sys", "user")
        assert res == {"raw_response": "Not a JSON string"}


@pytest.mark.asyncio
async def test_high_level_methods():
    manager = LLMManager()
    
    mock_generate_json = AsyncMock(return_value={"status": "mocked"})
    
    with patch.object(manager, "generate_json", mock_generate_json):
        # 1. Test analyze_webpage
        res_web = await manager.analyze_webpage("url", "instruction", "some html content")
        assert res_web == {"status": "mocked"}
        mock_generate_json.assert_called_once()
        mock_generate_json.reset_mock()

        # 2. Test analyze_error
        res_err = await manager.analyze_error("url", "instruction", {"old": "strategy"}, "error message", 1, 3)
        assert res_err == {"status": "mocked"}
        mock_generate_json.assert_called_once()
        mock_generate_json.reset_mock()

        # 3. Test clean_data
        res_clean = await manager.clean_data("instruction", "raw data content")
        assert res_clean == {"status": "mocked"}
        mock_generate_json.assert_called_once()
        mock_generate_json.reset_mock()

        # 4. Test generate_skill
        res_skill = await manager.generate_skill("https://example.com/page", "instruction", {"strat": "1"}, {"res": "2"})
        assert res_skill == {"status": "mocked"}
        mock_generate_json.assert_called_once()
