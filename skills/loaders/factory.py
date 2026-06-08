"""
技能載入器工廠（工廠模式）
根據格式類型創建對應的載入器
支持註冊新的載入器類型
"""
from typing import Dict, Type
from enum import Enum
from pathlib import Path
from .base import BaseSkillLoader
from .yaml_loader import YamlSkillLoader
from .json_loader import JsonSkillLoader


class SkillFormat(str, Enum):
    """技能格式枚舉"""
    YAML = "yaml"
    JSON = "json"


class SkillLoaderFactory:
    """
    技能載入器工廠
    根據格式類型創建對應的載入器
    支持註冊新的載入器類型
    """
    _loaders: Dict[SkillFormat, Type[BaseSkillLoader]] = {
        SkillFormat.YAML: YamlSkillLoader,
        SkillFormat.JSON: JsonSkillLoader,
    }

    @classmethod
    def create(cls, format_type: SkillFormat) -> BaseSkillLoader:
        """
        創建載入器
        參數:
            format_type: 格式類型
        回傳:
            對應的載入器實例
        """
        loader_class = cls._loaders.get(format_type)
        if not loader_class:
            raise ValueError(f"不支援的格式: {format_type}")
        return loader_class()

    @classmethod
    def register(cls, format_type: SkillFormat, loader_class: Type[BaseSkillLoader]):
        """
        註冊新載入器
        參數:
            format_type: 格式類型
            loader_class: 載入器類
        """
        cls._loaders[format_type] = loader_class

    @classmethod
    def get_loader_for_path(cls, path: Path) -> BaseSkillLoader:
        """
        根據路徑自動選擇載入器
        參數:
            path: 技能路徑
        回傳:
            適合的載入器
        """
        if path.is_dir():
            return cls.create(SkillFormat.YAML)
        elif path.suffix == '.json':
            return cls.create(SkillFormat.JSON)
        else:
            return cls.create(SkillFormat.YAML)

    @classmethod
    def get_all_formats(cls) -> list:
        """獲取所有支援的格式"""
        return list(cls._loaders.keys())
