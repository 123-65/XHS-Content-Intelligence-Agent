import json
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any

import httpx

from app.collectors.xhs.base import XhsCollectedNote, XhsCollectProviderResult, XhsUrlCollectProvider


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}
        self.scripts: list[str] = []
        self._in_script = False
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "meta":
            key = attrs_dict.get("property") or attrs_dict.get("name")
            content = attrs_dict.get("content")
            if key and content:
                self.meta[key] = unescape(content)
        if tag.lower() == "script":
            self._in_script = True
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_script:
            text = "".join(self._script_parts).strip()
            if text:
                self.scripts.append(text)
            self._in_script = False
            self._script_parts = []


class SimpleHttpXhsProvider(XhsUrlCollectProvider):
    provider_name = "simple_http_xhs"

    def collect(self, url: str, collect_comments: bool = True, max_comments: int = 20) -> XhsCollectProviderResult:
        try:
            response = httpx.get(
                url,
                follow_redirects=True,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; XHSGrowthAgent/1.0; public-page-collector)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
        except httpx.HTTPError as exc:
            return XhsCollectProviderResult(
                status="COLLECT_FAILED",
                provider_name=self.provider_name,
                source_url=url,
                error_code="HTTP_ERROR",
                error_message=str(exc),
            )

        if response.status_code in {401, 403}:
            return XhsCollectProviderResult(
                status="LOGIN_REQUIRED",
                provider_name=self.provider_name,
                source_url=url,
                error_code="LOGIN_REQUIRED",
                error_message=f"HTTP {response.status_code}",
                raw_text=response.text[:2000],
            )
        if response.status_code == 429:
            return XhsCollectProviderResult(
                status="RATE_LIMITED",
                provider_name=self.provider_name,
                source_url=url,
                error_code="RATE_LIMITED",
                error_message="HTTP 429",
                raw_text=response.text[:2000],
            )
        if response.status_code >= 400:
            return XhsCollectProviderResult(
                status="COLLECT_FAILED",
                provider_name=self.provider_name,
                source_url=url,
                error_code="HTTP_STATUS_ERROR",
                error_message=f"HTTP {response.status_code}",
                raw_text=response.text[:2000],
            )

        html = response.text
        if _looks_like_captcha(html):
            return XhsCollectProviderResult(
                status="CAPTCHA_REQUIRED",
                provider_name=self.provider_name,
                source_url=str(response.url),
                error_code="CAPTCHA_REQUIRED",
                error_message="The public page appears to require verification.",
                raw_html=html[:10000],
            )
        if _looks_like_login(html):
            return XhsCollectProviderResult(
                status="LOGIN_REQUIRED",
                provider_name=self.provider_name,
                source_url=str(response.url),
                error_code="LOGIN_REQUIRED",
                error_message="The public page appears to require login.",
                raw_html=html[:10000],
            )

        parsed = self._parse_html(str(response.url), html, collect_comments=collect_comments, max_comments=max_comments)
        if not any([parsed.title, parsed.content, parsed.author_name, parsed.image_urls]):
            return XhsCollectProviderResult(
                status="PARSE_FAILED",
                provider_name=self.provider_name,
                source_url=str(response.url),
                error_code="PARSE_FAILED",
                error_message="No reliable note content was found in the public HTML.",
                raw_html=html[:10000],
            )

        warnings = []
        for field in ("title", "content", "author_name"):
            if getattr(parsed, field) is None:
                warnings.append(f"MISSING_{field.upper()}")
        return XhsCollectProviderResult(
            status="SUCCESS" if not warnings else "PARTIAL_SUCCESS",
            provider_name=self.provider_name,
            source_url=str(response.url),
            raw_html=html[:20000],
            parsed_result=parsed,
            warnings=warnings,
        )

    def _parse_html(self, url: str, html: str, collect_comments: bool, max_comments: int) -> XhsCollectedNote:
        parser = _MetaParser()
        parser.feed(html)
        json_objects = _extract_json_objects(parser.scripts)
        title = _first_text(
            parser.meta.get("og:title"),
            parser.meta.get("twitter:title"),
            parser.meta.get("description"),
            *list(_walk_json_values(json_objects, ("title", "displayTitle", "noteTitle"))),
        )
        content = _first_text(
            parser.meta.get("og:description"),
            parser.meta.get("description"),
            *list(_walk_json_values(json_objects, ("desc", "description", "content"))),
        )
        author = _first_text(*list(_walk_json_values(json_objects, ("nickname", "nickName", "authorName", "userName"))))
        author_url = _first_text(*list(_walk_json_values(json_objects, ("userPage", "homepage", "authorHomepage"))))
        image_urls = _unique(
            [
                value
                for value in [
                    parser.meta.get("og:image"),
                    *list(_walk_json_values(json_objects, ("url", "imageUrl", "image_url", "coverUrl"))),
                ]
                if isinstance(value, str) and value.startswith(("http://", "https://"))
            ]
        )
        tags = _unique([value for value in _walk_json_values(json_objects, ("tag", "name")) if isinstance(value, str) and 0 < len(value) <= 64])[:20]
        comments = []
        if collect_comments:
            for index, item in enumerate(_walk_comment_objects(json_objects)):
                if index >= max_comments:
                    break
                text = _first_text(item.get("content"), item.get("text"))
                if text:
                    comments.append(
                        {
                            "content": text,
                            "like_count": _to_int(item.get("likeCount") or item.get("like_count")),
                            "author_name": _first_text(item.get("nickname"), item.get("userName")),
                            "comment_id": str(item.get("id") or item.get("commentId")) if item.get("id") or item.get("commentId") else None,
                            "raw_snapshot": item,
                        }
                    )
        return XhsCollectedNote(
            source_url=url,
            note_id=_extract_note_id(url),
            author_name=author,
            author_profile_url=author_url,
            title=title,
            content=content,
            content_summary=content[:200] if content else None,
            like_count=_first_int(*list(_walk_json_values(json_objects, ("likedCount", "likeCount", "likes")))),
            collect_count=_first_int(*list(_walk_json_values(json_objects, ("collectedCount", "collectCount", "collects")))),
            comment_count=_first_int(*list(_walk_json_values(json_objects, ("commentCount", "comments")))),
            share_count=_first_int(*list(_walk_json_values(json_objects, ("shareCount", "shares")))),
            cover_url=image_urls[0] if image_urls else None,
            image_urls=image_urls[:30],
            tags=tags,
            top_comments=comments,
            raw_snapshot={"meta": parser.meta, "json_object_count": len(json_objects)},
        )


def _looks_like_login(html: str) -> bool:
    text = html.lower()
    return "login" in text and ("登录" in html or "sign in" in text)


def _looks_like_captcha(html: str) -> bool:
    text = html.lower()
    return "captcha" in text or "验证码" in html or "安全验证" in html


def _extract_json_objects(scripts: list[str]) -> list[Any]:
    objects: list[Any] = []
    for script in scripts:
        candidates = []
        if "__INITIAL_STATE__" in script:
            candidates.append(script.split("=", 1)[-1].strip().rstrip(";"))
        if script.strip().startswith(("{", "[")):
            candidates.append(script.strip())
        for candidate in candidates:
            try:
                objects.append(json.loads(candidate))
            except json.JSONDecodeError:
                continue
    return objects


def _walk_json_values(items: list[Any], keys: tuple[str, ...]):
    key_set = set(keys)
    for item in items:
        yield from _walk_value(item, key_set)


def _walk_value(value: Any, keys: set[str]):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                yield item
            yield from _walk_value(item, keys)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_value(item, keys)


def _walk_comment_objects(items: list[Any]):
    for item in items:
        if isinstance(item, dict):
            keys = set(item)
            if {"content", "likeCount"} & keys and {"user", "nickname", "userName", "commentId", "id"} & keys:
                yield item
            for child in item.values():
                yield from _walk_comment_objects([child])
        elif isinstance(item, list):
            for child in item:
                yield from _walk_comment_objects([child])


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            text = re.sub(r"\s+", " ", unescape(value)).strip()
            if text:
                return text
    return None


def _first_int(*values: Any) -> int | None:
    for value in values:
        number = _to_int(value)
        if number is not None:
            return number
    return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        match = re.search(r"\d+", value.replace(",", ""))
        return int(match.group(0)) if match else None
    return None


def _extract_note_id(url: str) -> str | None:
    match = re.search(r"/(?:explore|discovery/item)/([^/?#]+)", url)
    return match.group(1) if match else None


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
