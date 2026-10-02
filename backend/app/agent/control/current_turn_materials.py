"""Deterministic normalization for external materials supplied in the current Turn."""

import re
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.unified_agent import AgentTurnMaterials


_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_MARKDOWN_URL_PATTERN = re.compile(r"\[[^\]]*\]\((https?://[^\s<>]+)\)", re.IGNORECASE)
_TRAILING_TEXT_PUNCTUATION = "。；，！？、"


class CurrentMaterialType(StrEnum):
    EXTERNAL_XHS_PROFILE = "EXTERNAL_XHS_PROFILE"
    EXTERNAL_XHS_NOTE = "EXTERNAL_XHS_NOTE"


class CurrentMaterialSource(StrEnum):
    CURRENT_TEXT = "CURRENT_TEXT"
    EXPLICIT_MATERIAL = "EXPLICIT_MATERIAL"
    BOTH = "BOTH"


class NormalizedCurrentMaterial(BaseModel):
    """One canonical current-turn material with deterministic provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    material_type: CurrentMaterialType
    source_url: str
    source: CurrentMaterialSource


class NormalizedTurnMaterials(BaseModel):
    """Internal normalization result; the public request contract stays unchanged."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    materials: AgentTurnMaterials
    items: list[NormalizedCurrentMaterial] = Field(default_factory=list)


class CurrentTurnMaterialNormalizer:
    """Convert raw Turn text into the existing typed material contract.

    This component is deliberately pure: it only extracts, classifies and preserves
    URLs. It never reads persistence or invokes providers, tools, or workflows.
    """

    def normalize(self, text: str, existing: AgentTurnMaterials | None = None) -> AgentTurnMaterials:
        return self.normalize_with_provenance(text, existing).materials

    def normalize_with_provenance(
        self,
        text: str,
        existing: AgentTurnMaterials | None = None,
    ) -> NormalizedTurnMaterials:
        existing = existing or AgentTurnMaterials()
        ordered: dict[tuple[CurrentMaterialType, str], CurrentMaterialSource] = {}

        for material_type, urls in (
            (CurrentMaterialType.EXTERNAL_XHS_NOTE, existing.note_urls),
            (CurrentMaterialType.EXTERNAL_XHS_PROFILE, existing.profile_urls),
        ):
            for url in urls:
                if self._classify(url) == material_type:
                    ordered[(material_type, url)] = CurrentMaterialSource.EXPLICIT_MATERIAL

        for url in self._urls_in_source_order(text):
            material_type = self._classify(url)
            if material_type is None:
                continue
            key = (material_type, url)
            ordered[key] = (
                CurrentMaterialSource.BOTH
                if ordered.get(key) == CurrentMaterialSource.EXPLICIT_MATERIAL
                else CurrentMaterialSource.CURRENT_TEXT
            )

        items = [
            NormalizedCurrentMaterial(material_type=material_type, source_url=url, source=source)
            for (material_type, url), source in ordered.items()
        ]
        return NormalizedTurnMaterials(
            materials=AgentTurnMaterials(
                note_urls=[item.source_url for item in items if item.material_type == CurrentMaterialType.EXTERNAL_XHS_NOTE],
                profile_urls=[item.source_url for item in items if item.material_type == CurrentMaterialType.EXTERNAL_XHS_PROFILE],
            ),
            items=items,
        )

    @classmethod
    def _urls_in_source_order(cls, text: str) -> list[str]:
        matches: list[tuple[int, str]] = []
        markdown_spans: list[tuple[int, int]] = []
        for match in _MARKDOWN_URL_PATTERN.finditer(text or ""):
            matches.append((match.start(1), match.group(1)))
            markdown_spans.append(match.span(1))

        for match in _URL_PATTERN.finditer(text or ""):
            if any(start <= match.start() < end for start, end in markdown_spans):
                continue
            matches.append((match.start(), cls._trim_plain_url(match.group(0))))

        matches.sort(key=lambda item: item[0])
        return cls._deduplicate([url for _, url in matches if url])

    @staticmethod
    def _trim_plain_url(value: str) -> str:
        value = value.rstrip(_TRAILING_TEXT_PUNCTUATION)
        while value.endswith(")") and value.count(")") > value.count("("):
            value = value[:-1]
        return value

    @staticmethod
    def _classify(value: str) -> CurrentMaterialType | None:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or host not in {"xiaohongshu.com", "www.xiaohongshu.com"}:
            return None
        if parsed.path.startswith("/user/profile/") and parsed.path.removeprefix("/user/profile/"):
            return CurrentMaterialType.EXTERNAL_XHS_PROFILE
        if parsed.path.startswith("/explore/") and parsed.path.removeprefix("/explore/"):
            return CurrentMaterialType.EXTERNAL_XHS_NOTE
        return None

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))
