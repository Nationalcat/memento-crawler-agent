"""
社區技能模組
提供標準化的技能格式、載入器和執行器
支援從本地目錄載入可分享的技能
"""
from skills.loaders import SkillLoaderFactory, SkillFormat
from skills.executor import CommunitySkillExecutor
from skills.models import CommunitySkill, Extractor, CrawlAction

__all__ = [
    "SkillLoaderFactory",
    "SkillFormat",
    "CommunitySkillExecutor",
    "CommunitySkill",
    "Extractor",
    "CrawlAction"
]
