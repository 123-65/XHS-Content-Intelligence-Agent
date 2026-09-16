from app.collectors.ocr.base import OcrProvider, OcrResult


class RapidOcrProvider(OcrProvider):
    """RapidOCR adapter; returns not-configured when the optional dependency is absent."""

    provider_name = "rapidocr"

    def __init__(self):
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
        except Exception:
            self.engine = None
        else:
            self.engine = RapidOCR()

    def extract_image_text(self, image_url: str) -> OcrResult:
        if self.engine is None:
            return OcrResult(status="OCR_PROVIDER_NOT_CONFIGURED", image_url=image_url, error_code="OCR_PROVIDER_NOT_CONFIGURED")
        try:
            result, _ = self.engine(image_url)
        except Exception as exc:
            return OcrResult(status="OCR_FAILED", image_url=image_url, error_code="OCR_FAILED", error_message=str(exc))
        lines = [str(item[1]).strip() for item in result or [] if len(item) >= 2 and str(item[1]).strip()]
        return OcrResult(status="SUCCESS", image_url=image_url, text="\n".join(lines) or None, lines=lines, raw_payload={"line_count": len(lines)})
