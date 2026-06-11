import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from utils.prompts import PromptLoader, prompt_loader


def test_prompts_loader_singleton():
    PromptLoader.reset()
    loader1 = PromptLoader()
    loader2 = PromptLoader()
    assert loader1 is loader2


def test_prompts_loader_load_missing_file():
    PromptLoader.reset()
    
    # Mock config_path.exists to return False
    with patch.object(Path, "exists", return_value=False):
        loader = PromptLoader()
        assert loader._prompts == {}


def test_prompts_loader_get_prompt_formatting():
    PromptLoader.reset()
    
    # Setup some test prompts directly
    loader = PromptLoader()
    loader._prompts = {
        "hello_prompt": {
            "system": "Hello {name}!",
            "user": "Tell me about {topic}."
        },
        "system_only": {
            "system": "System info"
        },
        "user_only": {
            "user": "User info"
        }
    }
    
    # 1. Successful formatting
    res = loader.get_prompt("hello_prompt", name="Alice", topic="AI")
    assert res["system"] == "Hello Alice!"
    assert res["user"] == "Tell me about AI."
    
    # 2. Key does not exist
    with pytest.raises(ValueError, match="提示詞 'nonexistent' 不存在"):
        loader.get_prompt("nonexistent")
        
    # 3. get_system_prompt & get_user_prompt helpers
    assert loader.get_system_prompt("system_only") == "System info"
    assert loader.get_user_prompt("system_only") == ""
    assert loader.get_system_prompt("user_only") == ""
    assert loader.get_user_prompt("user_only") == "User info"


def test_reload_and_reset():
    PromptLoader.reset()
    loader = PromptLoader()
    loader._prompts = {"old": {"system": "old_val"}}
    
    # Reload should read the yaml file (or set to empty if mocked as missing)
    with patch.object(Path, "exists", return_value=False):
        loader.reload()
        assert loader._prompts == {}
        
    # Reset should clear singleton
    PromptLoader.reset()
    assert PromptLoader._instance is None
    assert PromptLoader._prompts == {}
