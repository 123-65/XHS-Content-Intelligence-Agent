import re


SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；.!?;])\s*")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long_text(text: str, chunk_size: int) -> list[str]:
    return [text[index : index + chunk_size].strip() for index in range(0, len(text), chunk_size) if text[index : index + chunk_size].strip()]


def _semantic_units(text: str, chunk_size: int) -> list[str]:
    units: list[str] = []
    for paragraph in PARAGRAPH_SPLIT_RE.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= chunk_size:
            units.append(paragraph)
            continue
        sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(paragraph) if sentence.strip()]
        for sentence in sentences:
            if len(sentence) <= chunk_size:
                units.append(sentence)
            else:
                units.extend(_split_long_text(sentence, chunk_size))
    return units


def _overlap_tail(chunk: str, chunk_overlap: int) -> str:
    if chunk_overlap <= 0:
        return ""
    tail = chunk[-chunk_overlap:].strip()
    sentence_start = max(tail.rfind("。"), tail.rfind("！"), tail.rfind("？"), tail.rfind("."), tail.rfind("!"), tail.rfind("?"))
    if 0 <= sentence_start < len(tail) - 1:
        return tail[sentence_start + 1 :].strip()
    return tail


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    units = _semantic_units(normalized, chunk_size)
    chunks: list[str] = []
    current = ""

    for unit in units:
        separator = "\n\n" if "\n" in unit or "\n" in current else ""
        candidate = f"{current}{separator}{unit}".strip() if current else unit
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
            overlap = _overlap_tail(current, chunk_overlap)
            current = f"{overlap}\n\n{unit}".strip() if overlap else unit
            if len(current) > chunk_size:
                chunks.extend(_split_long_text(current, chunk_size))
                current = ""
        else:
            chunks.extend(_split_long_text(unit, chunk_size))

    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk]


def rough_token_count(text: str) -> int:
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other_chars = max(len(text) - chinese_chars, 0)
    return max(1, chinese_chars + other_chars // 4)
