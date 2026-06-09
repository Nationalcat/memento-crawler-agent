import pytest
import json
import yaml
from pathlib import Path
from typing import Optional, List
from skills.models import CommunitySkill, TargetConfig
from skills.loaders.base import BaseSkillLoader
from skills.loaders.yaml_loader import YamlSkillLoader
from skills.loaders.json_loader import JsonSkillLoader
from skills.loaders.factory import SkillLoaderFactory, SkillFormat

# 1. 建立 MockSkillLoader 來測試 BaseSkillLoader (模板模式基類) 的行為
class MockSkillLoader(BaseSkillLoader):
    def __init__(self):
        self.is_skill_val = True
        self.read_content_val = "mock content"
        self.parsed_data_val = {"id": "mock-skill", "name": "Mock Skill"}
        self.validate_val = True

    def _is_skill(self, path: Path) -> bool:
        return self.is_skill_val

    def _read_content(self, path: Path) -> Optional[str]:
        return self.read_content_val

    def _parse_content(self, content: str) -> Optional[dict]:
        return self.parsed_data_val

    def _build_skill(self, data: dict, path: Path) -> CommunitySkill:
        return CommunitySkill(
            id=data["id"],
            name=data["name"],
            target=TargetConfig(domain="example.com")
        )

    def _validate_skill(self, skill: CommunitySkill) -> bool:
        return self.validate_val


def test_base_skill_loader_flow(tmp_path):
    """測試 BaseSkillLoader 模板方法的執行流程"""
    loader = MockSkillLoader()
    
    # 建立測試目錄與檔案
    skill_dir = tmp_path / "skill-a"
    skill_dir.mkdir()
    (skill_dir / "dummy.txt").touch()

    # 1. 正常載入單個技能
    skill = loader.load_skill(skill_dir)
    assert skill is not None
    assert skill.id == "mock-skill"
    assert skill.name == "Mock Skill"

    # 2. 測試讀取失敗流程
    loader.read_content_val = None
    assert loader.load_skill(skill_dir) is None
    loader.read_content_val = "mock content"

    # 3. 測試解析失敗流程
    loader.parsed_data_val = None
    assert loader.load_skill(skill_dir) is None
    loader.parsed_data_val = {"id": "mock-skill", "name": "Mock Skill"}

    # 4. 測試驗證失敗流程
    loader.validate_val = False
    assert loader.load_skill(skill_dir) is None
    loader.validate_val = True

    # 5. 測試異常處理流程
    def raise_error(path):
        raise ValueError("Simulated read error")
    loader._read_content = raise_error
    assert loader.load_skill(skill_dir) is None


def test_base_skill_loader_load_all(tmp_path):
    """測試 BaseSkillLoader.load_all() 載入整個目錄"""
    loader = MockSkillLoader()
    
    # 建立多個目錄
    (tmp_path / "skill-1").mkdir()
    (tmp_path / "skill-2").mkdir()
    (tmp_path / ".hidden-dir").mkdir() # 隱藏目錄應被忽略
    
    skills = loader.load_all(tmp_path)
    assert len(skills) == 2
    assert skills[0].id == "mock-skill"

    # 測試非存在目錄應回傳空列表
    assert loader.load_all(tmp_path / "non-existent") == []


def test_yaml_skill_loader_behavior(tmp_path):
    """測試 YamlSkillLoader 對 SKILL.md 檔案的解析"""
    loader = YamlSkillLoader()
    
    # 測試非技能目錄
    empty_dir = tmp_path / "empty-dir"
    empty_dir.mkdir()
    assert loader._is_skill(empty_dir) is False

    # 測試技能目錄
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    
    yaml_header = {
        "id": "test-yaml-id",
        "name": "Test Yaml Name",
        "version": "1.2.0",
        "target": {
            "domain": "shopee.tw",
            "url_patterns": ["*/product/*"]
        }
    }
    
    # 寫入包含 YAML Frontmatter 及 Markdown Body 的 SKILL.md
    file_content = f"---\n{yaml.dump(yaml_header)}---\n# Test Prompt\nThis is prompt context."
    skill_file.write_text(file_content, encoding='utf-8')

    assert loader._is_skill(skill_dir) is True
    
    # 載入並驗證內容
    skill = loader.load_skill(skill_dir)
    assert skill is not None
    assert skill.id == "test-yaml-id"
    assert skill.name == "Test Yaml Name"
    assert skill.version == "1.2.0"
    assert skill.target.domain == "shopee.tw"
    assert skill.target.url_patterns == ["*/product/*"]
    assert skill.prompt == "# Test Prompt\nThis is prompt context."
    assert skill.skill_path == str(skill_dir)


def test_json_skill_loader_behavior(tmp_path):
    """測試 JsonSkillLoader 對 .json 檔案的解析"""
    loader = JsonSkillLoader()
    
    json_file = tmp_path / "skill-info.json"
    
    # 測試 _is_skill 檔名判斷
    assert loader._is_skill(tmp_path) is False
    json_file.touch()
    assert loader._is_skill(json_file) is True

    json_data = {
        "id": "test-json-id",
        "name": "Test Json Name",
        "version": "2.0.0",
        "target": {
            "domain": "amazon.com"
        },
        "prompt": "Json prompt text"
    }
    json_file.write_text(json.dumps(json_data), encoding='utf-8')
    
    skill = loader.load_skill(json_file)
    assert skill is not None
    assert skill.id == "test-json-id"
    assert skill.name == "Test Json Name"
    assert skill.version == "2.0.0"
    assert skill.target.domain == "amazon.com"
    assert skill.prompt == "Json prompt text"


def test_skill_loader_factory(tmp_path):
    """測試 SkillLoaderFactory 的建立與路徑偵測機制"""
    # 測試 create
    yaml_loader = SkillLoaderFactory.create(SkillFormat.YAML)
    assert isinstance(yaml_loader, YamlSkillLoader)

    json_loader = SkillLoaderFactory.create(SkillFormat.JSON)
    assert isinstance(json_loader, JsonSkillLoader)

    with pytest.raises(ValueError) as excinfo:
        SkillLoaderFactory.create("unsupported")
    assert "不支援的格式: unsupported" in str(excinfo.value)

    dir_path = tmp_path / "some-dir"
    dir_path.mkdir()
    assert isinstance(SkillLoaderFactory.get_loader_for_path(dir_path), YamlSkillLoader)

    json_file = tmp_path / "test.json"
    json_file.touch()
    assert isinstance(SkillLoaderFactory.get_loader_for_path(json_file), JsonSkillLoader)

    txt_file = tmp_path / "test.txt"
    txt_file.touch()
    assert isinstance(SkillLoaderFactory.get_loader_for_path(txt_file), YamlSkillLoader) # 預設為 YAML

def test_base_skill_loader_abc_methods():
    """測試 BaseSkillLoader 抽象基類各個 abstractmethod 的 pass，以達到 100% 覆蓋率"""
    class TestLoader(BaseSkillLoader):
        def _is_skill(self, path: Path) -> bool:
            return super()._is_skill(path)
        def _read_content(self, path: Path) -> Optional[str]:
            return super()._read_content(path)
        def _parse_content(self, content: str) -> Optional[dict]:
            return super()._parse_content(content)
        def _build_skill(self, data: dict, path: Path) -> CommunitySkill:
            return super()._build_skill(data, path)

    tl = TestLoader()
    # 呼叫這些方法，會執行到基類的 pass/沒有實作定義的行
    assert tl._is_skill(Path(".")) is None
    assert tl._read_content(Path(".")) is None
    assert tl._parse_content("") is None
    assert tl._build_skill({}, Path(".")) is None

def test_base_skill_loader_validation_failure():
    """測試 BaseSkillLoader 的 _validate_skill 驗證失敗情境"""
    class NativeValidationLoader(BaseSkillLoader):
        def _is_skill(self, path): return True
        def _read_content(self, path): return ""
        def _parse_content(self, content): return {}
        def _build_skill(self, data, path): return None
        
    tl = NativeValidationLoader()
    # 1. 傳入 None
    assert tl._validate_skill(None) is False
    
    # 2. 缺少 ID
    skill_no_id = CommunitySkill(id="", name="Valid Name", target=TargetConfig(domain="a.com"))
    assert tl._validate_skill(skill_no_id) is False
    
    # 3. 缺少 Name
    skill_no_name = CommunitySkill(id="valid-id", name="", target=TargetConfig(domain="a.com"))
    assert tl._validate_skill(skill_no_name) is False

def test_skill_loader_factory_registration():
    """測試 SkillLoaderFactory 的註冊新載入器與格式列表獲取"""
    class CustomFormatLoader(BaseSkillLoader):
        def _is_skill(self, path): return True
        def _read_content(self, path): return ""
        def _parse_content(self, content): return {}
        def _build_skill(self, data, path): return None
        
    # 註冊新格式
    SkillLoaderFactory.register("custom_format", CustomFormatLoader)
    assert "custom_format" in SkillLoaderFactory.get_all_formats()
    
    custom_loader = SkillLoaderFactory.create("custom_format")
    assert isinstance(custom_loader, CustomFormatLoader)

def test_json_skill_loader_exceptions(tmp_path):
    """測試 JsonSkillLoader 的異常處理分支 (讀取失敗、解析失敗)"""
    loader = JsonSkillLoader()
    # 1. 讀取一個非檔案路徑（如目錄），會引發 PermissionError 等異常
    assert loader._read_content(tmp_path) is None

    # 2. 解析無效 JSON 格式
    assert loader._parse_content("{invalid-json}") is None

def test_yaml_skill_loader_edge_cases(tmp_path):
    """測試 YamlSkillLoader 的異常處理與無分隔符之解析"""
    loader = YamlSkillLoader()
    
    # 1. _is_skill 傳入非目錄路徑
    file_path = tmp_path / "dummy.txt"
    file_path.touch()
    assert loader._is_skill(file_path) is False

    # 2. _read_content 檔案不存在時應回傳 None
    non_existent = tmp_path / "non-existent-dir"
    assert loader._read_content(non_existent) is None

    # 3. _parse_content 檔案內容不含 YAML 分隔符 "---"
    plain_content = "id: test-id\nname: test-name"
    parsed = loader._parse_content(plain_content)
    assert parsed is not None
    assert parsed["yaml"]["id"] == "test-id"
    assert parsed["prompt"] == ""

def test_nested_extractors_parsing():
    """測試 YamlSkillLoader 與 JsonSkillLoader 處理嵌套 extractor 的解析"""
    # 測試 YamlSkillLoader 嵌套
    yaml_loader = YamlSkillLoader()
    yaml_ext_data = [
        {
            "name": "parent",
            "selector": ".parent-class",
            "type": "text",
            "children": [
                {"name": "child", "selector": ".child-class", "type": "text"}
            ]
        }
    ]
    parsed_yaml_exts = yaml_loader._parse_extractors(yaml_ext_data)
    assert len(parsed_yaml_exts) == 1
    assert parsed_yaml_exts[0].name == "parent"
    assert len(parsed_yaml_exts[0].children) == 1
    assert parsed_yaml_exts[0].children[0].name == "child"

    # 測試 JsonSkillLoader 嵌套
    json_loader = JsonSkillLoader()
    parsed_json_exts = json_loader._parse_extractors(yaml_ext_data)
    assert len(parsed_json_exts) == 1
    assert parsed_json_exts[0].name == "parent"
    assert len(parsed_json_exts[0].children) == 1
    assert parsed_json_exts[0].children[0].name == "child"

