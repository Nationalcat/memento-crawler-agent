"""
技能模組
匯出技能相關的類別和函數
支援兩種技能格式：
1. 結構化技能（SKILL.md 格式）
2. 自動生成技能（JSON 格式）
"""
from .memory import SkillMemory
from .models import (
    CommunitySkill,
    Extractor,
    CrawlAction,
    Parameter,
    TargetConfig,
    ExecutionConfig,
    OutputConfig
)
from .loaders import (
    BaseSkillLoader,
    YamlSkillLoader,
    JsonSkillLoader,
    SkillLoaderFactory,
    SkillFormat
)
from .executor import CommunitySkillExecutor, generate_skill_from_execution
from .strategy import CrawlStrategy, StrategyRegistry
from .base import BaseSkill

__all__ = [
    # 記憶庫
    "SkillMemory",

    # 模型
    "CommunitySkill",
    "Extractor",
    "CrawlAction",
    "Parameter",
    "TargetConfig",
    "ExecutionConfig",
    "OutputConfig",

    # 載入器（模板模式 + 工廠模式）
    "BaseSkillLoader",
    "YamlSkillLoader",
    "JsonSkillLoader",
    "SkillLoaderFactory",
    "SkillFormat",

    # 執行器
    "CommunitySkillExecutor",
    "generate_skill_from_execution",

    # 策略模式
    "CrawlStrategy",
    "StrategyRegistry",

    # 基礎類
    "BaseSkill"
]
