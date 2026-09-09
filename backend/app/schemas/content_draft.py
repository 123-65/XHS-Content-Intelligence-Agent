from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ImageScript(BaseModel):
    """小红书图片脚本。"""

    index: int = Field(ge=1, description="第几张图")
    title: str = Field(description="图片标题")
    content: str = Field(description="图片正文内容")
    visual_hint: str | None = Field(default=None, description="画面建议")


class DraftGenerateResult(BaseModel):
    """模型生成的内容草稿结构。"""

    title: str = Field(description="小红书标题")
    body: str = Field(description="小红书正文")
    tags: list[str] = Field(description="小红书标签")
    cover_text: str = Field(description="封面文案")
    image_scripts: list[ImageScript] = Field(description="每张图片写什么")
    cta: str = Field(description="转化引导语")


class GenerateDraftRequest(BaseModel):
    """生成内容草稿请求。"""

    experiment_id: int
    user_requirement: str | None = Field(default=None, description="用户额外要求")
    use_mock: bool = Field(default=True, description="是否使用模拟生成，开发阶段默认 True")


class ContentDraftCreate(BaseModel):
    """创建内容草稿数据。"""

    experiment_id: int
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    cover_text: str | None = None
    image_scripts: list[dict] = Field(default_factory=list)
    cta: str | None = None
    version: int = 1
    status: str = "GENERATED"
    generation_context: dict = Field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: Decimal = Decimal("0")
    raw_response_id: str | None = None


class ContentDraftResponse(BaseModel):
    """内容草稿响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    title: str
    body: str
    tags: list[str]
    cover_text: str | None
    image_scripts: list[dict]
    cta: str | None
    version: int
    status: str
    generation_context: dict
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    raw_response_id: str | None
    created_at: datetime
    updated_at: datetime
