"""
社區技能執行器模組
負責執行結構化技能（SKILL.md 格式）
支援 helper.py 動態載入和執行
支援多種提取器（文字、屬性、列表、嵌套）
"""
import importlib.util
import re
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from .models import CommunitySkill, Extractor, CrawlAction


class CommunitySkillExecutor:
    """
    社區技能執行器
    執行結構化技能，支援：
    - 基本資料提取
    - 列表提取
    - 嵌套提取
    - helper.py 動態載入
    """

    def __init__(self, skill: CommunitySkill):
        """
        初始化執行器
        參數:
            skill: 技能實例
        """
        self.skill = skill
        self.helper_module = None

        # 載入 helper.py（如果有）
        if skill.script_path and Path(skill.script_path).exists():
            self._load_helper(skill.script_path)

    def _load_helper(self, script_path: str):
        """
        動態載入 helper.py
        參數:
            script_path: 腳本路徑
        """
        try:
            spec = importlib.util.spec_from_file_location("helper", script_path)
            self.helper_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.helper_module)
        except Exception as e:
            print(f"載入 helper.py 失敗: {e}")
            self.helper_module = None

    async def execute(self, url: str, params: Dict = None) -> Dict:
        """
        執行技能
        參數:
            url: 目標網址
            params: 執行參數
        回傳:
            執行結果
        """
        # 合併參數
        exec_params = self._merge_params(params or {})

        # 如果有 helper.py，調用其 execute 函數
        if self.helper_module and hasattr(self.helper_module, 'execute'):
            try:
                result = await self.helper_module.execute(url, exec_params, self.skill)
                return result
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"helper.py 執行失敗: {str(e)}",
                    "data": []
                }

        # 否則使用預設執行邏輯
        return await self._default_execute(url, exec_params)

    async def _default_execute(self, url: str, params: Dict) -> Dict:
        """
        預設執行邏輯
        參數:
            url: 目標網址
            params: 執行參數
        回傳:
            執行結果
        """
        # 這裡需要與瀏覽器整合
        # 實際執行時會由 ExecutorAgent 調用
        return {
            "status": "success",
            "data": [],
            "skill_id": self.skill.id,
            "extractors": [ext.model_dump() for ext in self.skill.extractors],
            "execution_config": self.skill.execution.model_dump()
        }

    def _merge_params(self, params: Dict) -> Dict:
        """
        合併預設參數和用戶參數
        參數:
            params: 用戶參數
        回傳:
            合併後的參數
        """
        result = {}
        for param in self.skill.parameters:
            if param.name in params:
                result[param.name] = params[param.name]
            elif param.default is not None:
                result[param.name] = param.default
            elif param.required:
                raise ValueError(f"缺少必要參數: {param.name}")
        return result

    def extract_data(self, html_content: str) -> List[Dict[str, Any]]:
        """
        使用提取器從 HTML 中提取資料
        參數:
            html_content: HTML 內容
        回傳:
            提取的資料列表
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, 'html.parser')
        results = []

        # 檢查是否有 multiple 提取器
        has_multiple = any(ext.multiple for ext in self.skill.extractors)

        if has_multiple:
            # 列表提取模式
            results = self._extract_list(soup)
        else:
            # 單一提取模式
            result = self._extract_single(soup)
            if result:
                results.append(result)

        return results

    def _extract_single(self, soup) -> Optional[Dict[str, Any]]:
        """
        單一提取模式
        參數:
            soup: BeautifulSoup 對象
        回傳:
            提取的資料，或 None
        """
        result = {}
        has_data = False

        for extractor in self.skill.extractors:
            value = self._extract_value(soup, extractor)
            if value is not None:
                result[extractor.name] = value
                has_data = True
            elif extractor.required:
                return None

        return result if has_data else None

    def _extract_list(self, soup) -> List[Dict[str, Any]]:
        """
        列表提取模式
        參數:
            soup: BeautifulSoup 對象
        回傳:
            提取的資料列表
        """
        # 檢查是否含有嵌套提取器 (hierarchical structure)
        has_children = any(getattr(ext, 'children', None) for ext in self.skill.extractors) or (
            any(ext.multiple for ext in self.skill.extractors) and any(not ext.multiple for ext in self.skill.extractors)
        )

        if not has_children:
            # 扁平結構：使用 zip 方式並行提取所有欄位的值 (與 _extract_with_strategy 邏輯一致)
            results = []
            extracted_fields = {}
            max_len = 0
            for extractor in self.skill.extractors:
                if not extractor.selector:
                    continue
                elements = soup.select(extractor.selector)
                values = []
                for el in elements:
                    value = self._extract_element_value(el, extractor)
                    if value is not None:
                        values.append(value)
                extracted_fields[extractor.name] = values
                max_len = max(max_len, len(values))

            if max_len > 0:
                for i in range(max_len):
                    item = {}
                    for extractor in self.skill.extractors:
                        values = extracted_fields.get(extractor.name, [])
                        if i < len(values):
                            item[extractor.name] = values[i]
                        else:
                            item[extractor.name] = None
                    results.append(item)
            return results

        # 嵌套結構：原有的父子層級列表提取模式
        # 找到第一個 multiple 提取器作為列表基準
        main_extractor = None
        for ext in self.skill.extractors:
            if ext.multiple:
                main_extractor = ext
                break

        if not main_extractor:
            return []

        # 獲取所有匹配的元素
        elements = soup.select(main_extractor.selector)
        if not elements:
            return []

        results = []
        for element in elements:
            item = {}
            for extractor in self.skill.extractors:
                if extractor.multiple:
                    # 對於 multiple 提取器，使用當前元素的值
                    value = self._extract_element_value(element, extractor)
                else:
                    # 對於非 multiple 提取器，在父元素中查找
                    parent = element.parent
                    if parent:
                        value = self._extract_value(parent, extractor)
                    else:
                        value = None

                if value is not None:
                    item[extractor.name] = value

            if item:
                results.append(item)

        return results

    def _extract_value(self, element, extractor: Extractor) -> Any:
        """
        從元素中提取值
        參數:
            element: HTML 元素
            extractor: 提取器配置
        回傳:
            提取的值
        """
        # 查找目標元素
        target = element.select_one(extractor.selector)
        if not target:
            return None

        return self._extract_element_value(target, extractor)

    def _extract_element_value(self, element, extractor: Extractor) -> Any:
        """
        從元素中提取值（直接使用元素）
        參數:
            element: HTML 元素
            extractor: 提取器配置
        回傳:
            提取的值
        """
        # 獲取原始值
        if extractor.type == "text":
            value = element.get_text(strip=True)
        elif extractor.type == "attribute" and extractor.attribute:
            value = element.get(extractor.attribute)
        elif extractor.type == "html":
            value = str(element)
        elif extractor.type == "value":
            value = element.get("value")
        else:
            value = element.get_text(strip=True)

        if value is None:
            return None

        # 應用正則表達式
        if extractor.regex:
            match = re.search(extractor.regex, str(value))
            if match:
                value = match.group(1) if match.groups() else match.group(0)
            else:
                return None

        # 應用轉換
        if extractor.transform:
            value = self._apply_transform(value, extractor.transform)

        # 處理嵌套提取器
        if extractor.children:
            nested_results = []
            for child_ext in extractor.children:
                child_value = self._extract_value(element, child_ext)
                if child_value is not None:
                    nested_results.append(child_value)
            if nested_results:
                value = nested_results

        return value

    def _apply_transform(self, value: Any, transform: str) -> Any:
        """
        應用資料轉換
        參數:
            value: 原始值
            transform: 轉換表達式
        回傳:
            轉換後的值
        """
        try:
            # 安全的轉換函數
            if "replace" in transform:
                # 處理 replace 函數
                match = re.search(r"replace\(/(.+)/,\s*'(.+)'\)", transform)
                if match:
                    pattern = match.group(1)
                    replacement = match.group(2)
                    value = re.sub(pattern, replacement, str(value))

            # 嘗試轉換為數字
            if isinstance(value, str):
                try:
                    if "." in value:
                        return float(value)
                    return int(value)
                except ValueError:
                    pass

            return value
        except Exception:
            return value


def generate_skill_from_execution(
    skill_id: str,
    skill_name: str,
    url: str,
    instruction: str,
    extractors: List[Dict],
    execution_config: Dict,
    code: str = None,
    prompt: str = None
) -> CommunitySkill:
    """
    從執行結果生成技能
    參數:
        skill_id: 技能 ID
        skill_name: 技能名稱
        url: 目標網址
        instruction: 用戶指令
        extractors: 提取器配置
        execution_config: 執行配置
        code: 執行代碼（可選）
        prompt: 提示詞（可選）
    回傳:
        生成的技能實例
    """
    from urllib.parse import urlparse
    from .models import TargetConfig, Parameter, ExecutionConfig, Extractor, OutputConfig

    # 解析域名
    parsed = urlparse(url)
    domain = parsed.netloc

    # 構建目標配置
    target = TargetConfig(
        domain=domain,
        url_patterns=[f"{domain}/*"]
    )

    # 構建提取器
    skill_extractors = []
    for ext_data in extractors:
        skill_extractors.append(Extractor(
            name=ext_data.get("name", ""),
            selector=ext_data.get("selector", ""),
            type=ext_data.get("type", "text"),
            required=ext_data.get("required", False),
            transform=ext_data.get("transform"),
            regex=ext_data.get("regex"),
            attribute=ext_data.get("attribute"),
            multiple=ext_data.get("multiple", True)
        ))

    # 構建執行配置
    execution = ExecutionConfig(
        wait_time=execution_config.get("wait_time", 2),
        scroll=execution_config.get("scroll", False),
        headless=execution_config.get("headless", True)
    )

    # 生成提示詞
    if not prompt:
        prompt = f"""# {skill_name}

## 任務說明
{instruction}

## 目標網站
{url}

## 提取欄位
"""
        for ext in skill_extractors:
            prompt += f"- {ext.name}: {ext.selector}\n"

    return CommunitySkill(
        id=skill_id,
        name=skill_name,
        version="1.0.0",
        author="auto-generated",
        description=f"自動生成的爬蟲技能 - {instruction}",
        tags=["auto-generated"],
        target=target,
        parameters=[],
        execution=execution,
        extractors=skill_extractors,
        output=OutputConfig(format="json"),
        prompt=prompt,
        is_auto_generated=True
    )
