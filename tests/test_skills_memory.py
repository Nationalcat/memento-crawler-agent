import pytest
import json
import yaml
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open
from skills.models import CommunitySkill, TargetConfig, Parameter
from skills.memory import SkillMemory

from config import settings
# Override database URL to use in-memory SQLite for testing
settings.DATABASE_URL = "sqlite:///:memory:"

from database.connection import Base, engine, SessionLocal

@pytest.fixture(autouse=True)
def setup_memory(tmp_path):
    """每個測試執行前，重置 SkillMemory 單例，並使用獨立的臨時資料夾與記憶體資料庫"""
    Base.metadata.create_all(bind=engine)
    SkillMemory.reset()
    SkillMemory._community_dir = tmp_path / "community"
    SkillMemory._auto_dir = tmp_path / "data"
    yield
    Base.metadata.drop_all(bind=engine)
    SkillMemory.reset()

def test_singleton_pattern():
    """測試 SkillMemory 的單例模式"""
    m1 = SkillMemory()
    m2 = SkillMemory()
    assert m1 is m2

def test_load_all_skills_empty():
    """測試初始化空技能庫"""
    memory = SkillMemory()
    assert len(memory.get_all_skills()) == 0
    assert len(memory.get_community_skills()) == 0
    assert len(memory.get_auto_skills()) == 0

def test_load_auto_skills_malformed_json(tmp_path):
    """測試載入自動技能時，若 JSON 損毀應能捕獲異常並跳過"""
    auto_dir = tmp_path / "data"
    auto_dir.mkdir(parents=True, exist_ok=True)
    
    # 寫入損毀的 JSON
    bad_file = auto_dir / "bad.json"
    bad_file.write_text("{invalid_json}", encoding="utf-8")
    
    # 初始化 SkillMemory 應該正常，且不載入壞檔案
    memory = SkillMemory()
    assert len(memory.get_auto_skills()) == 0

def test_store_and_retrieve_community_skill(tmp_path):
    """測試儲存與檢索結構化 CommunitySkill 技能"""
    memory = SkillMemory()
    
    skill = CommunitySkill(
        id="test-skill-domain",
        name="Domain Matcher",
        version="1.0.0",
        description="Matches a domain",
        tags=["shop", "test"],
        target=TargetConfig(domain="shopee.tw", url_patterns=["*/product/*"]),
        prompt="grab pricing info",
        script_path="scripts/helper.py" # 觸發 script_path 存在的分支
    )
    
    memory.store_community_skill(skill)
    
    # 1. 檢查檔案是否確實寫入
    md_file = tmp_path / "community" / "test-skill-domain" / "SKILL.md"
    assert md_file.exists()
    
    # 2. 測試 retrieve_skill (URL 模式匹配)
    # 2a. 域名匹配
    res1 = memory.retrieve_skill("https://shopee.tw/some/path")
    assert res1 is skill
    
    # 2b. URL Pattern 匹配
    res2 = memory.retrieve_skill("https://other-domain.com/product/123")
    assert res2 is skill
    
    # 2c. 未匹配
    res3 = memory.retrieve_skill("https://google.com")
    assert res3 is None

def test_store_and_retrieve_auto_skill():
    """測試儲存與檢索自動生成 JSON 技能"""
    memory = SkillMemory()
    
    skill_data = {
        "id": "auto_123",
        "name": "Auto Example",
        "target_domain": "amazon.com",
        "selectors": {"price": ".price-tag"}
    }
    
    memory.store_auto_skill(skill_data)
    
    # 1. 檢索 (域名包含/被包含)
    res = memory.retrieve_skill("https://www.amazon.com/dp/123")
    assert res == skill_data
    
    # 測試 domain 被 target_domain 包含
    res_sub = memory.retrieve_skill("https://amazon/dp/123")
    assert res_sub == skill_data

    # 未匹配
    assert memory.retrieve_skill("https://ebay.com") is None

def test_store_auto_skill_write_exception():
    """測試儲存自動技能時寫入檔案發生異常"""
    memory = SkillMemory()
    skill_data = {"id": "auto_fail", "name": "Fail"}
    
    # 藉由將 _auto_dir 變更為一個檔案，來強制 open 拋出 Exception
    memory._auto_dir.mkdir(parents=True, exist_ok=True)
    fake_dir_file = memory._auto_dir / "auto_fail.json"
    fake_dir_file.mkdir() # 建立為資料夾使 open 寫入失敗
    
    # 應該能正常執行而不當機，且記憶體有寫入
    memory.store_auto_skill(skill_data)
    assert memory._auto_skills["auto_fail"] == skill_data

def test_update_community_skill():
    """測試更新結構化技能與版本號累加"""
    memory = SkillMemory()
    
    # 格式 1: 標準三碼版本 (1.0.0 -> 1.0.1)
    skill = CommunitySkill(
        id="yaml-skill",
        name="Yaml",
        version="1.0.0",
        target=TargetConfig(domain="domain.com")
    )
    memory.store_community_skill(skill)
    memory.update_community_skill(skill)
    assert skill.version == "1.0.1"
    
    # 格式 2: 非標準雙碼版本 (1.0 -> 1.0.1)
    skill2 = CommunitySkill(
        id="yaml-skill-2",
        name="Yaml 2",
        version="1.0",
        target=TargetConfig(domain="domain2.com")
    )
    memory.store_community_skill(skill2)
    memory.update_community_skill(skill2)
    assert skill2.version == "1.0.1"

def test_update_auto_skill():
    """測試更新自動生成技能"""
    memory = SkillMemory()
    skill_data = {"id": "auto_1", "name": "Name1"}
    
    memory.store_auto_skill(skill_data)
    
    updated_data = {"id": "auto_1", "name": "Name2"}
    memory.update_auto_skill(updated_data)
    
    assert memory._auto_skills["auto_1"]["name"] == "Name2"

def test_search_skills():
    """測試搜尋技能（Community 與 Auto）"""
    memory = SkillMemory()
    
    # 建立 Community Skill
    c_skill = CommunitySkill(
        id="yaml-shop",
        name="Shopee Scraper",
        description="Scrapes shop info",
        tags=["ecom", "spider"],
        target=TargetConfig(domain="shopee.tw")
    )
    memory.store_community_skill(c_skill)
    
    # 建立 Auto Skill
    a_skill = {
        "id": "auto-shop",
        "name": "Momo Price Grabber",
        "description": "grabs prices from momo"
    }
    memory.store_auto_skill(a_skill)
    
    # 1. 以名稱搜尋 (匹配 Momo)
    res_name = memory.search_skills("momo")
    assert len(res_name) == 1
    assert res_name[0]["id"] == "auto-shop"
    
    # 2. 以描述搜尋 (匹配 Scrapes)
    res_desc = memory.search_skills("scraper")
    assert len(res_desc) == 1
    assert res_desc[0].id == "yaml-shop"
    
    # 3. 以 Tag 搜尋 (匹配 spider)
    res_tag = memory.search_skills("spider")
    assert len(res_tag) == 1
    assert res_tag[0].id == "yaml-shop"

def test_delete_skill(tmp_path):
    """測試刪除技能與對應檔案"""
    memory = SkillMemory()
    
    # 1. 刪除 Community Skill
    c_skill = CommunitySkill(
        id="del-yaml",
        name="To Delete",
        target=TargetConfig(domain="del.com")
    )
    memory.store_community_skill(c_skill)
    c_dir = tmp_path / "community" / "del-yaml"
    assert c_dir.exists()
    
    deleted_c = memory.delete_skill("del-yaml")
    assert deleted_c is True
    assert "del-yaml" not in memory._community_skills
    assert not c_dir.exists()

    # 2. 刪除 Auto Skill
    a_skill = {"id": "del-auto", "name": "To Delete"}
    memory.store_auto_skill(a_skill)
    a_file = tmp_path / "data" / "del-auto.json"
    assert a_file.exists()
    
    deleted_a = memory.delete_skill("del-auto")
    assert deleted_a is True
    assert "del-auto" not in memory._auto_skills
    assert not a_file.exists()

    # 3. 刪除不存在的技能，回傳 False
    assert memory.delete_skill("non-existent") is False

def test_load_pre_existing_skills_from_directories(tmp_path):
    """測試在初始化時，SkillMemory 自動載入現有資料夾內的技能"""
    # 由於 setup_memory 已經重置了 SkillMemory，我們在這裡手動建立檔案，然後再呼叫實例化。
    # 1. 建立現有的 community 技能 (SKILL.md)
    c_dir = tmp_path / "community" / "exist-yaml"
    c_dir.mkdir(parents=True, exist_ok=True)
    c_file = c_dir / "SKILL.md"
    yaml_header = {
        "id": "exist-yaml",
        "name": "Exist Yaml Name",
        "version": "1.0.0",
        "target": {"domain": "exist.com"}
    }
    c_file.write_text(f"---\n{yaml.dump(yaml_header)}---\nprompt text", encoding="utf-8")

    # 2. 建立現有的 auto 技能 (.json)
    a_dir = tmp_path / "data"
    a_dir.mkdir(parents=True, exist_ok=True)
    a_file = a_dir / "exist-auto.json"
    json_data = {"id": "exist-auto", "name": "Exist Auto Name", "target_domain": "auto.com"}
    a_file.write_text(json.dumps(json_data), encoding="utf-8")

    # 3. 實例化 SkillMemory，這會觸發載入行為
    memory = SkillMemory()
    
    # 4. 驗證是否正確載入
    assert "exist-yaml" in memory._community_skills
    assert memory._community_skills["exist-yaml"].name == "Exist Yaml Name"
    assert "exist-auto" in memory._auto_skills
    assert memory._auto_skills["exist-auto"]["name"] == "Exist Auto Name"

