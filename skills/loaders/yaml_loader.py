"""
YAML 格式技能載入器
實現 SKILL.md (YAML + Markdown) 格式的解析
"""
import yaml
from typing import Optional, List, Dict
from pathlib import Path
from .base import BaseSkillLoader
from skills.models import (
    CommunitySkill, TargetConfig, Parameter,
    ExecutionConfig, Extractor, OutputConfig, CrawlAction
)


class YamlSkillLoader(BaseSkillLoader):
    """
    YAML 格式技能載入器
    處理 SKILL.md 格式：YAML 頭部 + Markdown 正文
    """

    def _is_skill(self, path: Path) -> bool:
        """判斷是否是 YAML 技能目錄（包含 SKILL.md）"""
        if path.is_dir():
            return (path / "SKILL.md").exists()
        return False

    def _read_content(self, path: Path) -> Optional[str]:
        """讀取 SKILL.md 內容"""
        skill_file = path / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding='utf-8')
        return None

    def _parse_content(self, content: str) -> Optional[dict]:
        """解析 YAML + Markdown 格式"""
        parts = content.split("---", 2)

        if len(parts) >= 3:
            # 第二部分是 YAML 配置，第三部分是 Markdown 提示詞
            yaml_content = parts[1].strip()
            prompt_content = parts[2].strip()
            yaml_data = yaml.safe_load(yaml_content) or {}
            return {"yaml": yaml_data, "prompt": prompt_content}
        else:
            # 整個文件作為 YAML
            yaml_data = yaml.safe_load(content) or {}
            return {"yaml": yaml_data, "prompt": ""}

    def _build_skill(self, data: dict, path: Path) -> CommunitySkill:
        """構建 CommunitySkill 對象"""
        yaml_data = data.get("yaml", {})

        # 解析目標配置
        target = self._parse_target(yaml_data.get("target", {}))

        # 解析參數
        parameters = self._parse_parameters(yaml_data.get("parameters", []))

        # 解析執行配置
        execution = self._parse_execution(yaml_data.get("execution", {}))

        # 解析提取器
        extractors = self._parse_extractors(yaml_data.get("extractors", []))

        # 解析輸出配置
        output = self._parse_output(yaml_data.get("output", {}))

        # 檢查 helper.py
        helper_path = path / "scripts" / "helper.py"
        script_path = str(helper_path) if helper_path.exists() else None

        return CommunitySkill(
            id=yaml_data.get("id", path.name),
            name=yaml_data.get("name", path.name),
            version=yaml_data.get("version", "1.0.0"),
            author=yaml_data.get("author", "community"),
            description=yaml_data.get("description", ""),
            tags=yaml_data.get("tags", []),
            target=target,
            parameters=parameters,
            execution=execution,
            extractors=extractors,
            output=output,
            prompt=data.get("prompt", ""),
            skill_path=str(path),
            script_path=script_path
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
