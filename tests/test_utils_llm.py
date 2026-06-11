import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from utils.llm import LLMManager, llm_manager, LLMFactory, OpenAIAdapter, OllamaAdapter, LLMAdapter
from config import settings


def test_singleton_pattern():
    manager1 = LLMManager()
    manager2 = LLMManager()
    assert manager1 is manager2


def test_init_llm_branches():
    manager = LLMManager()
    
    # 1. API key is empty/None
    with patch.object(settings, "LLM_PROVIDER", "openai"):
        with patch.object(settings, "LLM_API_KEY", None):
            manager._init_llm()
            assert manager._llm is None
        
    # 2. API key is set
    with patch.object(settings, "LLM_PROVIDER", "openai"):
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
        state = {"prompts": []}
        res_web = await manager.analyze_webpage("url", "instruction", "some html content", state=state)
        assert res_web == {"status": "mocked"}
        assert len(state["prompts"]) == 1
        assert state["prompts"][0]["type"] == "analyze_webpage"
        assert len(state["prompts"][0]["system"]) > 0
        mock_generate_json.assert_called_once()
        mock_generate_json.reset_mock()

        # 2. Test analyze_error
        state = {"prompts": []}
        res_err = await manager.analyze_error("url", "instruction", {"old": "strategy"}, "error message", 1, 3, state=state)
        assert res_err == {"status": "mocked"}
        assert len(state["prompts"]) == 1
        assert state["prompts"][0]["type"] == "analyze_error"
        mock_generate_json.assert_called_once()
        mock_generate_json.reset_mock()

        # 3. Test clean_data
        state = {"prompts": []}
        res_clean = await manager.clean_data("instruction", "raw data content", state=state)
        assert res_clean == {"status": "mocked"}
        assert len(state["prompts"]) == 1
        assert state["prompts"][0]["type"] == "clean_data"
        mock_generate_json.assert_called_once()
        mock_generate_json.reset_mock()

        # 4. Test generate_skill
        state = {"prompts": []}
        res_skill = await manager.generate_skill("https://example.com/page", "instruction", {"strat": "1"}, {"res": "2"}, state=state)
        assert res_skill == {"status": "mocked"}
        assert len(state["prompts"]) == 1
        assert state["prompts"][0]["type"] == "generate_skill"
        mock_generate_json.assert_called_once()


@pytest.mark.asyncio
async def test_llm_factory_and_adapters():
    # 0. Test abstract LLMAdapter generate method directly to cover it
    assert await LLMAdapter.generate(None, "sys", "user") is None

    # 1. Test factory get_adapter with invalid provider
    with pytest.raises(ValueError, match="未支援的 LLM 提供者"):
        LLMFactory.get_adapter("invalid_provider")

    # 2. Test factory with openai provider (no API key)
    with patch.object(settings, "LLM_PROVIDER", "openai"):
        with patch.object(settings, "LLM_API_KEY", None):
            adapter = LLMFactory.get_adapter("openai")
            assert adapter is None

    # 3. Test factory with openai provider (with API key)
    with patch.object(settings, "LLM_PROVIDER", "openai"):
        with patch.object(settings, "LLM_API_KEY", "mock-key"):
            with patch("utils.llm.ChatOpenAI") as mock_chat:
                adapter = LLMFactory.get_adapter("openai")
                assert adapter is not None
                mock_chat.assert_called_once()

    # 4. Test OpenAIAdapter generate method
    with patch("utils.llm.ChatOpenAI") as mock_chat:
        mock_instance = MagicMock()
        mock_chat.return_value = mock_instance
        mock_response = MagicMock()
        mock_response.content = "openai generated response"
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)

        adapter = OpenAIAdapter("gpt-4", "mock-key")
        result = await adapter.generate("sys", "user")
        assert result == "openai generated response"
        mock_instance.ainvoke.assert_called_once()

    # 5. Test factory with ollama provider
    with patch.object(settings, "LLM_PROVIDER", "ollama"):
        with patch.object(settings, "LLM_BASE_URL", "http://localhost:11434/v1"):
            with patch("utils.llm.ChatOpenAI") as mock_chat:
                adapter = LLMFactory.get_adapter("ollama")
                assert adapter is not None
                mock_chat.assert_called_once_with(
                    model=settings.LLM_MODEL,
                    api_key="ollama",
                    base_url="http://localhost:11434/v1",
                    temperature=0.1,
                    max_tokens=1024,
                    timeout=90.0
                )

    # 6. Test OllamaAdapter generate method
    with patch("utils.llm.ChatOpenAI") as mock_chat:
        mock_instance = MagicMock()
        mock_chat.return_value = mock_instance
        mock_response = MagicMock()
        mock_response.content = "ollama generated response"
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)

        adapter = OllamaAdapter("llama3", "http://localhost:11434/v1")
        result = await adapter.generate("sys", "user")
        assert result == "ollama generated response"
        mock_instance.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_llm_manager_with_adapters():
    manager = LLMManager()

    # Test initialization with invalid provider
    with patch.object(settings, "LLM_PROVIDER", "invalid"):
        manager._init_llm()
        assert manager._adapter is None
        assert manager._llm is None

    # Test initialization with ollama provider
    with patch.object(settings, "LLM_PROVIDER", "ollama"):
        with patch.object(settings, "LLM_BASE_URL", "http://localhost:11434/v1"):
            with patch("utils.llm.ChatOpenAI") as mock_chat:
                manager._init_llm()
                assert manager._adapter is not None
                assert manager._llm is not None

    # Test generate delegation to adapter
    mock_adapter = MagicMock()
    mock_adapter.generate = AsyncMock(return_value="delegated result")
    mock_adapter._llm = "mock-llm-instance"
    
    manager._adapter = mock_adapter
    manager._llm = "mock-llm-instance"  # matching the adapter's _llm reference
    
    res = await manager.generate("sys", "user")
    assert res == "delegated result"
    mock_adapter.generate.assert_called_once_with("sys", "user")

