"""
JSON 格式技能載入器
實現純 JSON 格式的解析
與 YAML 格式結構相同，只是文件格式不同
"""
import json
from typing import Optional, List, Dict
from pathlib import Path
from .base import BaseSkillLoader
from skills.models import (
    CommunitySkill, TargetConfig, Parameter,
    ExecutionConfig, Extractor, OutputConfig, CrawlAction
)


class JsonSkillLoader(BaseSkillLoader):
    """
    JSON 格式技能載入器
    處理 .json 格式的技能文件
    """

    def _is_skill(self, path: Path) -> bool:
        """判斷是否是 JSON 技能文件"""
        return path.is_file() and path.suffix == '.json'

    def _read_content(self, path: Path) -> Optional[str]:
        """讀取 JSON 文件內容"""
        try:
            return path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"讀取 JSON 文件失敗 {path}: {e}")
            return None

    def _parse_content(self, content: str) -> Optional[dict]:
        """解析 JSON 內容"""
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"解析 JSON 失敗: {e}")
            return None

    def _build_skill(self, data: dict, path: Path) -> CommunitySkill:
        """構建 CommunitySkill 對象"""
        # 解析目標配置
        target = self._parse_target(data.get("target", {}))

        # 解析參數
        parameters = self._parse_parameters(data.get("parameters", []))

        # 解析執行配置
        execution = self._parse_execution(data.get("execution", {}))

        # 解析提取器
        extractors = self._parse_extractors(data.get("extractors", []))

        # 解析輸出配置
        output = self._parse_output(data.get("output", {}))

        return CommunitySkill(
            id=data.get("id", path.stem),
            name=data.get("name", path.stem),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "community"),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            target=target,
            parameters=parameters,
            execution=execution,
            extractors=extractors,
            output=output,
            prompt=data.get("prompt", ""),
            skill_path=str(path),
            script_path=data.get("script_path")
        )

    def _parse_target(self, data: Dict) -> TargetConfig:
        """解析目標配置"""
        return TargetConfig(
            domain=data.get("domain", ""),
            url_patterns=data.get("url_patterns", [])
        )

    def _parse_parameters(self, data: List[Dict]) -> List[Parameter]:
        """解析參數列表"""
        return [Parameter(**p) for p in data]

    def _parse_execution(self, data: Dict) -> ExecutionConfig:
        """解析執行配置"""
        actions = [CrawlAction(**a) for a in data.get("actions", [])]
        return ExecutionConfig(
            wait_time=data.get("wait_time", 2),
            scroll=data.get("scroll", False),
            headless=data.get("headless", True),
            actions=actions
        )

    def _parse_extractors(self, data: List[Dict]) -> List[Extractor]:
        """解析提取器（支援嵌套）"""
        extractors = []
        for ext_data in data:
            children = None
            if "children" in ext_data:
                children = self._parse_extractors(ext_data["children"])

            extractors.append(Extractor(
                name=ext_data.get("name", ""),
                selector=ext_data.get("selector", ""),
                type=ext_data.get("type", "text"),
                required=ext_data.get("required", False),
                transform=ext_data.get("transform"),
                regex=ext_data.get("regex"),
                attribute=ext_data.get("attribute"),
                multiple=ext_data.get("multiple", False),
                children=children
            ))
        return extractors

    def _parse_output(self, data: Dict) -> OutputConfig:
        """解析輸出配置"""
        return OutputConfig(
            format=data.get("format", "json"),
            output_schema=data.get("schema", {})
        )
