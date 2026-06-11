"""
資料庫模型定義
"""
import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from database.connection import Base
from skills.models import CommunitySkill, TargetConfig, Parameter, ExecutionConfig, Extractor, OutputConfig


class DBSkill(Base):
    """
    爬蟲技能資料庫模型
    將結構化技能儲存於 SQLite 資料庫中，欄位對應 CommunitySkill Pydantic 模型
    """
    __tablename__ = "skills"

    id = Column(String, primary_key=True, index=True)         # 技能唯一識別碼
    name = Column(String, nullable=False)                      # 技能名稱
    version = Column(String, default="1.0.0")                  # 版本號
    author = Column(String, default="auto-generated")          # 作者
    description = Column(String, default="")                   # 技能描述
    tags = Column(Text, default="[]")                          # 標籤 (JSON 陣列字串)
    target = Column(Text, default="{}")                        # 目標網站配置 (JSON 字串)
    parameters = Column(Text, default="[]")                    # 輸入參數列表 (JSON 陣列字串)
    execution = Column(Text, default="{}")                     # 執行配置 (JSON 字串)
    extractors = Column(Text, default="[]")                    # 資料提取器列表 (JSON 陣列字串)
    output = Column(Text, default="{}")                        # 輸出配置 (JSON 字串)
    prompt = Column(Text, default="")                          # 提示詞模板
    is_auto_generated = Column(Boolean, default=True)          # 是否為自動生成的技能
    created_at = Column(DateTime, default=datetime.utcnow)     # 建立時間
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) # 最後更新時間

    def to_pydantic(self) -> CommunitySkill:
        """
        將資料庫模型轉換為 Pydantic CommunitySkill 實例
        """
        try:
            tags_list = json.loads(self.tags) if self.tags else []
        except Exception:
            tags_list = []

        try:
            target_dict = json.loads(self.target) if self.target else {}
            target = TargetConfig(**target_dict)
        except Exception:
            target = TargetConfig(domain="")

        try:
            params_list = json.loads(self.parameters) if self.parameters else []
            parameters = [Parameter(**p) for p in params_list]
        except Exception:
            parameters = []

        try:
            exec_dict = json.loads(self.execution) if self.execution else {}
            execution = ExecutionConfig(**exec_dict)
        except Exception:
            execution = ExecutionConfig()

        try:
            ext_list = json.loads(self.extractors) if self.extractors else []
            # Extractor needs model_rebuild() but it is already called in skills.models
            extractors = [Extractor(**e) for e in ext_list]
        except Exception:
            extractors = []

        try:
            out_dict = json.loads(self.output) if self.output else {}
            output = OutputConfig(**out_dict)
        except Exception:
            output = OutputConfig()

        return CommunitySkill(
            id=self.id,
            name=self.name,
            version=self.version,
            author=self.author,
            description=self.description,
            tags=tags_list,
            target=target,
            parameters=parameters,
            execution=execution,
            extractors=extractors,
            output=output,
            prompt=self.prompt or "",
            is_auto_generated=self.is_auto_generated
        )

    @classmethod
    def from_pydantic(cls, skill: CommunitySkill) -> "DBSkill":
        """
        從 Pydantic CommunitySkill 實例建立資料庫模型
        """
        return cls(
            id=skill.id,
            name=skill.name,
            version=skill.version,
            author=skill.author,
            description=skill.description,
            tags=json.dumps(skill.tags, ensure_ascii=False),
            target=json.dumps(skill.target.model_dump(), ensure_ascii=False),
            parameters=json.dumps([p.model_dump() for p in skill.parameters], ensure_ascii=False),
            execution=json.dumps(skill.execution.model_dump(), ensure_ascii=False),
            extractors=json.dumps([e.model_dump() for e in skill.extractors], ensure_ascii=False),
            output=json.dumps(skill.output.model_dump(), ensure_ascii=False),
            prompt=skill.prompt,
            is_auto_generated=skill.is_auto_generated
        )


class DBCrawlResult(Base):
    """
    爬取結果資料庫模型
    儲存爬取成功的任務詳細資料與抓取結果
    """
    __tablename__ = "crawl_results"

    id = Column(Integer, primary_key=True, autoincrement=True)  # 自增識別碼
    task_id = Column(String, index=True, nullable=False)        # 任務唯一識別碼
    url = Column(String, nullable=False)                        # 目標網址
    instruction = Column(Text, nullable=False)                  # 爬取指令
    extracted_data = Column(Text, nullable=False)               # 提取出的資料 (JSON 陣列字串)
    created_at = Column(DateTime, default=datetime.utcnow)      # 建立時間
