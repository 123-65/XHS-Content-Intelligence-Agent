from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


OcrStatus = Literal["SUCCESS", "OCR_PROVIDER_NOT_CONFIGURED", "OCR_FAILED", "IMAGE_FETCH_FAILED"]


class OcrResult(BaseModel):
    status: OcrStatus
    image_url: str
    text: str | None = None
    lines: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    raw_payload: dict = Field(default_factory=dict)


class OcrProvider(ABC):
    provider_name = "base_ocr_provider"

    @abstractmethod
    def extract_image_text(self, image_url: str) -> OcrResult:
        """Recognize text from one public image URL."""
