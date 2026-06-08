"""
技能載入器基類（模板模式）
定義技能載入的演算法骨架，子類別實現具體解析邏輯
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path
from skills.models import CommunitySkill


class BaseSkillLoader(ABC):
    """
    技能載入器基類
    使用模板模式定義載入流程：
    1. load_all() - 載入所有技能（模板方法）
    2. load_skill() - 載入單個技能（模板方法）
    3. 子類別實現 _is_skill, _read_content, _parse_content, _build_skill
    """

    def load_all(self, directory: Path) -> List[CommunitySkill]:
        """
        模板方法：載入所有技能
        掃描目錄，對每個項目判斷是否是技能並載入
        參數:
            directory: 技能目錄路徑
        回傳:
            技能列表
        """
        skills = []
        if not directory.exists():
            return skills

        for item in sorted(directory.iterdir()):
            # 跳過隱藏文件/目錄
            if item.name.startswith('.'):
                continue

            # 判斷是否是技能
            if self._is_skill(item):
                skill = self.load_skill(item)
                if skill:
                    skills.append(skill)

        return skills

    def load_skill(self, path: Path) -> Optional[CommunitySkill]:
        """
        模板方法：載入單個技能
        流程：讀取 → 解析 → 構建 → 驗證
        參數:
            path: 技能路徑
        回傳:
            技能實例，或 None
        """
        try:
            # 1. 讀取內容
            content = self._read_content(path)
            if not content:
                return None

            # 2. 解析內容
            parsed_data = self._parse_content(content)
            if not parsed_data:
                return None

            # 3. 構建技能對象
            skill = self._build_skill(parsed_data, path)

            # 4. 驗證技能
            if not self._validate_skill(skill):
                return None

            return skill

        except Exception as e:
            print(f"載入技能失敗 {path}: {e}")
            return None

    # ====== 抽象方法（子類別必須實現）======

    @abstractmethod
    def _is_skill(self, path: Path) -> bool:
        """
        判斷是否是技能
        參數:
            path: 文件或目錄路徑
        回傳:
            是否是技能
        """
        pass

    @abstractmethod
    def _read_content(self, path: Path) -> Optional[str]:
        """
        讀取技能內容
        參數:
            path: 技能路徑
        回傳:
            內容字符串，或 None
        """
        pass

    @abstractmethod
    def _parse_content(self, content: str) -> Optional[dict]:
        """
        解析技能內容
        參數:
            content: 原始內容
        回傳:
            解析後的數據字典，或 None
        """
        pass

    @abstractmethod
    def _build_skill(self, data: dict, path: Path) -> CommunitySkill:
        """
        構建技能對象
        參數:
            data: 解析後的數據
            path: 技能路徑
        回傳:
            CommunitySkill 實例
        """
        pass

    def _validate_skill(self, skill: CommunitySkill) -> bool:
        """
        驗證技能（可選重寫）
        參數:
            skill: 技能實例
        回傳:
            是否有效
        """
        if not skill:
            return False
        if not skill.id or not skill.name:
            return False
        return True
