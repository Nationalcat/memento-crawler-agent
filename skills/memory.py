"""
技能記憶庫模組
實作 Memento-Skills 架構中的技能儲存與檢索功能
使用單例模式確保全域只有一個技能記憶庫
支援兩種技能格式：
1. 結構化技能（SKILL.md 格式）- 保存到 skills/community/
2. 自動生成技能（JSON 格式）- 保存到 skills/data/
"""
import json
import yaml
from typing import Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime
from config import settings

from .models import CommunitySkill
from .loaders import SkillLoaderFactory, SkillFormat


class SkillMemory:
    """
    技能記憶庫（單例模式）
    管理兩種格式的技能：
    - 結構化技能（CommunitySkill）：手動創建或社區分享
    - 自動生成技能（JSON）：LLM 自動生成
    """
    _instance: Optional['SkillMemory'] = None

    # 結構化技能（SKILL.md 格式）
    _community_skills: Dict[str, CommunitySkill] = {}

    # 自動生成技能（JSON 格式）
    _auto_skills: Dict[str, Dict] = {}

    # 目錄配置
    _community_dir: Path = Path("skills/community")
    _auto_dir: Path = Path(settings.SKILLS_DATA_DIR)

    def __new__(cls):
        """單例模式實作"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._community_dir.mkdir(parents=True, exist_ok=True)
            cls._instance._auto_dir.mkdir(parents=True, exist_ok=True)
            cls._instance._load_all_skills()
        return cls._instance

    def _load_all_skills(self):
        """載入所有技能"""
        self._load_community_skills()
        self._load_auto_skills()

    def _load_community_skills(self):
        """載入結構化技能"""
        loader = SkillLoaderFactory.create(SkillFormat.YAML)
        skills = loader.load_all(self._community_dir)
        for skill in skills:
            self._community_skills[skill.id] = skill

    def _load_auto_skills(self):
        """載入自動生成技能"""
        for skill_file in self._auto_dir.glob("*.json"):
            try:
                with open(skill_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._auto_skills[data.get("id", skill_file.stem)] = data
            except Exception as e:
                print(f"載入自動技能失敗 {skill_file}: {e}")

    def retrieve_skill(self, url: str) -> Optional[Union[CommunitySkill, Dict]]:
        """
        根據網址檢索對應技能
        優先查找結構化技能，再查找自動生成技能
        參數:
            url: 目標網址
        回傳:
            匹配的技能，或 None
        """
        # 1. 先查找結構化技能
        loader = SkillLoaderFactory.create(SkillFormat.YAML)
        for skill in self._community_skills.values():
            if self._match_url(url, skill):
                return skill

        # 2. 再查找自動生成技能
        from utils import BrowserManager
        domain = BrowserManager.extract_domain(url)

        for skill in self._auto_skills.values():
            target_domain = skill.get("target_domain", "")
            if target_domain in domain or domain in target_domain:
                return skill

        return None

    def _match_url(self, url: str, skill: CommunitySkill) -> bool:
        """
        判斷 URL 是否匹配技能
        參數:
            url: 目標網址
            skill: 技能實例
        回傳:
            是否匹配
        """
        import re
        url_lower = url.lower()

        # 匹配域名
        domain = skill.target.domain.lower()
        if domain and domain in url_lower:
            return True

        # 匹配 URL 模式
        for pattern in skill.target.url_patterns:
            regex_pattern = pattern.lower().replace("*", ".*")
            if re.search(regex_pattern, url_lower):
                return True

        return False

    def store_community_skill(self, skill: CommunitySkill) -> None:
        """
        儲存結構化技能
        參數:
            skill: 技能實例
        """
        self._community_skills[skill.id] = skill
        self._save_community_skill(skill)

    def _save_community_skill(self, skill: CommunitySkill):
        """
        儲存結構化技能到文件
        參數:
            skill: 技能實例
        """
        skill_dir = self._community_dir / skill.id
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 生成 SKILL.md
        skill_md_content = self._generate_skill_md(skill)
        skill_md_path = skill_dir / "SKILL.md"
        skill_md_path.write_text(skill_md_content, encoding='utf-8')

        # 生成 helper.py（如果有代碼）
        if skill.script_path:
            # 複製現有的 helper.py
            pass

    def _generate_skill_md(self, skill: CommunitySkill) -> str:
        """
        生成 SKILL.md 內容
        參數:
            skill: 技能實例
        回傳:
            SKILL.md 內容
        """
        # YAML 頭部
        yaml_data = {
            "id": skill.id,
            "name": skill.name,
            "version": skill.version,
            "author": skill.author,
            "description": skill.description,
            "tags": skill.tags,
            "target": {
                "domain": skill.target.domain,
                "url_patterns": skill.target.url_patterns
            },
            "parameters": [p.model_dump() for p in skill.parameters],
            "execution": skill.execution.model_dump(),
            "extractors": [e.model_dump() for e in skill.extractors],
            "output": skill.output.model_dump()
        }

        yaml_content = yaml.dump(yaml_data, allow_unicode=True, default_flow_style=False)

        # 組合
        return f"---\n{yaml_content}---\n\n{skill.prompt}"

    def store_auto_skill(self, skill_data: Dict) -> None:
        """
        儲存自動生成技能
        參數:
            skill_data: 技能數據
        """
        skill_id = skill_data.get("id")
        self._auto_skills[skill_id] = skill_data
        self._save_auto_skill(skill_data)

    def _save_auto_skill(self, skill_data: Dict):
        """
        儲存自動生成技能到文件
        參數:
            skill_data: 技能數據
        """
        skill_id = skill_data.get("id")
        file_path = self._auto_dir / f"{skill_id}.json"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(skill_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"儲存自動技能失敗 {file_path}: {e}")

    def update_community_skill(self, skill: CommunitySkill) -> None:
        """
        更新結構化技能（版本 +1）
        參數:
            skill: 技能實例
        """
        if skill.id in self._community_skills:
            # 版本 +1
            version_parts = skill.version.split(".")
            if len(version_parts) >= 3:
                version_parts[2] = str(int(version_parts[2]) + 1)
            else:
                version_parts.append("1")
            skill.version = ".".join(version_parts)

            self._community_skills[skill.id] = skill
            self._save_community_skill(skill)

    def update_auto_skill(self, skill_data: Dict) -> None:
        """
        更新自動生成技能
        參數:
            skill_data: 技能數據
        """
        skill_id = skill_data.get("id")
        if skill_id in self._auto_skills:
            self._auto_skills[skill_id] = skill_data
            self._save_auto_skill(skill_data)

    def search_skills(self, query: str) -> List[Union[CommunitySkill, Dict]]:
        """
        搜尋技能
        參數:
            query: 搜尋關鍵字
        回傳:
            符合條件的技能列表
        """
        results = []
        query_lower = query.lower()

        # 搜尋結構化技能
        for skill in self._community_skills.values():
            if (query_lower in skill.name.lower() or 
                query_lower in skill.description.lower() or
                query_lower in [t.lower() for t in skill.tags]):
                results.append(skill)

        # 搜尋自動生成技能
        for skill in self._auto_skills.values():
            name = skill.get("name", "").lower()
            description = skill.get("description", "").lower()
            if query_lower in name or query_lower in description:
                results.append(skill)

        return results

    def get_all_skills(self) -> List[Union[CommunitySkill, Dict]]:
        """
        獲取所有技能
        回傳:
            所有技能的列表
        """
        skills = []
        skills.extend(self._community_skills.values())
        skills.extend(self._auto_skills.values())
        return skills

    def get_community_skills(self) -> List[CommunitySkill]:
        """
        獲取所有結構化技能
        回傳:
            結構化技能列表
        """
        return list(self._community_skills.values())

    def get_auto_skills(self) -> List[Dict]:
        """
        獲取所有自動生成技能
        回傳:
            自動生成技能列表
        """
        return list(self._auto_skills.values())

    def delete_skill(self, skill_id: str) -> bool:
        """
        刪除技能（自動判斷類型）
        參數:
            skill_id: 技能識別碼
        回傳:
            是否刪除成功
        """
        # 先嘗試刪除結構化技能
        if skill_id in self._community_skills:
            del self._community_skills[skill_id]
            skill_dir = self._community_dir / skill_id
            if skill_dir.exists():
                import shutil
                shutil.rmtree(skill_dir)
            return True

        # 再嘗試刪除自動生成技能
        if skill_id in self._auto_skills:
            del self._auto_skills[skill_id]
            file_path = self._auto_dir / f"{skill_id}.json"
            if file_path.exists():
                file_path.unlink()
            return True

        return False

    @classmethod
    def reset(cls) -> None:
        """重置技能記憶庫（用於測試）"""
        cls._instance = None
        cls._community_skills = {}
        cls._auto_skills = {}
