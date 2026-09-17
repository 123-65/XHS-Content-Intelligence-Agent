import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.collectors.xhs.base import XhsCollectedAccount, XhsCollectedComment, XhsCollectedNote


_SENSITIVE_KEY_PARTS = (
    "xsectoken",
    "accesstoken",
    "refreshtoken",
    "authorization",
    "cookie",
    "session",
)
_SENSITIVE_QUERY_RE = re.compile(
    r"(?i)((?:xsec[_-]?token|access[_-]?token|refresh[_-]?token|authorization|session)[=:])([^&\s\"'<>]+)"
)


def sanitize_xhs_payload(value: Any) -> Any:
    """Remove authentication material before provider payloads can be persisted or logged."""
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
                continue
            sanitized[key] = sanitize_xhs_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_xhs_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_xhs_payload(item) for item in value]
    if isinstance(value, str):
        return _SENSITIVE_QUERY_RE.sub(r"\1***", value)
    return value


def normalize_note_payload(payload: dict[str, Any], *, source_url: str, provider_name: str, source_type: str) -> XhsCollectedNote:
    payload = sanitize_xhs_payload(payload)
    container = _unwrap(payload, "data", "feed")
    data = _unwrap(container, "note")
    note_card = _mapping(_first(data, "note_card", "noteCard"))
    if note_card:
        data = {**data, **note_card}
    author = _mapping(_first(data, "user", "user_info", "userInfo", "author"))
    interact = _mapping(_first(data, "interact_info", "interactInfo", "note_interact_info", "noteInteractInfo"))
    comment_items = _list(
        _first(payload, "comments", "comment_list", "commentList")
        or _first(container, "comments", "comment_list", "commentList")
        or _first(data, "comments", "comment_list", "commentList", "top_comments")
    )
    comments = [
        normalize_comment_payload(item, note_url=source_url)
        for item in comment_items
        if isinstance(item, dict)
    ]
    author_id = _text(_first(author, "user_id", "userId", "id") or _first(data, "author_id", "user_id", "userId"))
    profile_url = _text(_first(data, "author_profile_url", "author_homepage", "profile_url"))
    if not profile_url and author_id:
        profile_url = f"https://www.xiaohongshu.com/user/profile/{author_id}"
    image_urls = _image_urls(_first(data, "image_list", "imageList", "images_list", "images", "image_urls"))
    tags = _tag_names(_first(data, "tag_list", "tagList", "tags"))
    return XhsCollectedNote(
        note_url=source_url,
        source_url=source_url,
        source_type=source_type,
        source_provider=provider_name,
        provider_name=provider_name,
        status="SUCCESS",
        note_id=_text(_first(data, "note_id", "noteId", "feed_id", "feedId", "id")),
        author_id=author_id,
        title=_text(_first(data, "title", "display_title", "displayTitle")),
        content=_text(_first(data, "content", "desc", "description")),
        content_summary=_text(_first(data, "content_summary", "summary")),
        author_name=_text(_first(author, "nickname", "nick_name", "name") or _first(data, "author_name", "nickname")),
        author_profile_url=profile_url,
        publish_time=_datetime(_first(data, "publish_time", "publishTime", "created_at", "time", "timestamp")),
        like_count=_int(_first(interact, "liked_count", "likedCount", "like_count", "likes") or _first(data, "like_count", "liked_count")),
        collect_count=_int(_first(interact, "collected_count", "collectedCount", "collect_count", "collects") or _first(data, "collect_count", "collected_count")),
        comment_count=_int(_first(interact, "comment_count", "commentCount", "comments_count") or _first(data, "comment_count", "comments_count")),
        share_count=_int(_first(interact, "share_count", "shareCount", "sharedCount", "shares") or _first(data, "share_count", "shares")),
        cover_url=_cover_url(data, image_urls),
        image_urls=image_urls,
        image_ocr_texts=_string_list(_first(data, "image_ocr_texts", "ocr_texts")),
        card_structure=_dict_list(_first(data, "card_structure")),
        tags=tags,
        comments=comments,
        raw_payload=payload,
        raw_snapshot=payload,
        warnings=[str(item) for item in _list(_first(payload, "warnings") or _first(data, "warnings"))],
    )


def normalize_account_payload(payload: dict[str, Any], *, source_url: str, provider_name: str, source_type: str) -> XhsCollectedAccount:
    payload = sanitize_xhs_payload(payload)
    data = _unwrap(payload, "account", "data", "profile")
    basic = _mapping(_first(data, "basic_info", "basicInfo", "userBasicInfo", "user", "user_info", "userInfo")) or data
    counts = _interaction_counts(_first(data, "interactions", "interaction_info", "interactionInfo"))
    recent_items = _list(_first(data, "feeds", "notes", "recent_notes", "recentNotes", "items"))
    account_id = (
        _text(_first(basic, "user_id", "userId", "account_id", "id"))
        or _recent_note_author_id(recent_items)
        or _profile_id(source_url)
        or _text(_first(basic, "red_id", "redId"))
    )
    recent_notes = [
        _normalize_recent_note(item, provider_name=provider_name, source_type=source_type)
        for item in recent_items
        if isinstance(item, dict)
    ]
    return XhsCollectedAccount(
        account_id=account_id,
        external_user_id=account_id,
        profile_url=source_url,
        nickname=_text(_first(basic, "nickname", "nick_name", "name")),
        avatar_url=_avatar_url(_first(basic, "avatar_url", "avatar", "image", "images")),
        bio=_text(_first(basic, "bio", "desc", "description")),
        follower_count=_int(_first(data, "follower_count", "followers", "fans") or counts.get("followers")),
        following_count=_int(_first(data, "following_count", "following", "follows") or counts.get("following")),
        liked_count=_int(_first(data, "liked_count", "likes_received", "likes") or counts.get("liked")),
        recent_notes=recent_notes,
        raw_payload=payload,
        source_provider=provider_name,
        provider_name=provider_name,
        source_type=source_type,
        status="SUCCESS",
        warnings=[str(item) for item in _list(_first(payload, "warnings") or _first(data, "warnings"))],
    )


def normalize_comment_payload(payload: dict[str, Any], *, note_url: str | None = None) -> XhsCollectedComment:
    author = _mapping(_first(payload, "user_info", "userInfo", "user", "author"))
    return XhsCollectedComment(
        comment_id=_text(_first(payload, "comment_id", "commentId", "id")),
        note_id=_text(_first(payload, "note_id", "noteId", "feed_id", "feedId")),
        note_url=_text(_first(payload, "note_url", "noteUrl")) or note_url,
        author_id=_text(_first(author, "user_id", "userId", "id") or _first(payload, "author_id", "user_id", "userId")),
        author_name=_text(_first(author, "nickname", "nick_name", "name") or _first(payload, "author_name", "nickname", "user_name")),
        content=_text(_first(payload, "content", "text")) or "",
        like_count=_int(_first(payload, "like_count", "likeCount", "likes")),
        created_at=_datetime(_first(payload, "created_at", "create_time", "createTime", "publish_time", "time")),
        raw_snapshot=payload,
    )


def _normalize_recent_note(item: dict[str, Any], *, provider_name: str, source_type: str) -> XhsCollectedNote:
    note_id = _text(_first(item, "note_id", "noteId", "feed_id", "feedId", "id"))
    note_card = _mapping(_first(item, "note_card", "noteCard"))
    payload = {**item, **note_card} if note_card else item
    source_url = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
    return normalize_note_payload(payload, source_url=source_url, provider_name=provider_name, source_type=source_type)


def _unwrap(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, dict):
        nested = _first(value, "list", "items", "comments")
        return nested if isinstance(nested, list) else []
    return value if isinstance(value, list) else []


def _recent_note_author_id(items: list[Any]) -> str | None:
    for item in items:
        if not isinstance(item, dict):
            continue
        note_card = _mapping(_first(item, "note_card", "noteCard")) or item
        user = _mapping(_first(note_card, "user", "user_info", "userInfo", "author"))
        if user_id := _text(_first(user, "user_id", "userId", "id")):
            return user_id
    return None


def _profile_id(source_url: str) -> str | None:
    parts = [part for part in urlparse(source_url).path.split("/") if part]
    if "profile" not in parts:
        return None
    index = parts.index("profile")
    return parts[index + 1] if index + 1 < len(parts) else None


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if value >= 0 else None
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    if not match:
        return None
    number = float(match.group(0))
    multiplier = 100_000_000 if "亿" in normalized else 10_000 if "万" in normalized or normalized.lower().endswith("w") else 1
    return int(number * multiplier)


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)) and value > 0:
        timestamp = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(timestamp)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        if value.strip().isdigit():
            return _datetime(int(value.strip()))
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _image_urls(value: Any) -> list[str]:
    urls: list[str] = []
    for item in _list(value):
        if isinstance(item, str) and item.strip():
            urls.append(item.strip())
            continue
        if not isinstance(item, dict):
            continue
        candidate = _text(_first(item, "url", "url_default", "urlDefault", "original", "original_url"))
        if not candidate:
            info_items = _list(_first(item, "info_list", "infoList"))
            candidate = next((_text(_first(info, "url")) for info in info_items if isinstance(info, dict) and _text(_first(info, "url"))), None)
        if candidate:
            urls.append(candidate)
    return list(dict.fromkeys(urls))


def _cover_url(data: dict[str, Any], image_urls: list[str]) -> str | None:
    cover = _first(data, "cover_url", "coverUrl", "cover")
    if isinstance(cover, dict):
        cover = _first(cover, "url", "url_default", "urlDefault")
    return _text(cover) or (image_urls[0] if image_urls else None)


def _tag_names(value: Any) -> list[str]:
    result: list[str] = []
    for item in _list(value):
        text = _text(_first(item, "name", "title")) if isinstance(item, dict) else _text(item)
        if text:
            result.append(text)
    return result


def _avatar_url(value: Any) -> str | None:
    if isinstance(value, list):
        return next((_avatar_url(item) for item in value if _avatar_url(item)), None)
    if isinstance(value, dict):
        return _text(_first(value, "url", "url_default", "urlDefault"))
    return _text(value)


def _interaction_counts(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in _list(value):
        if not isinstance(item, dict):
            continue
        kind = (_text(_first(item, "type", "name")) or "").lower()
        count = _first(item, "count", "value")
        if kind in {"fans", "followers", "follower"}:
            result["followers"] = count
        elif kind in {"follows", "following", "follow"}:
            result["following"] = count
        elif kind in {"interaction", "interactions", "liked", "likes"}:
            result["liked"] = count
    return result


def _string_list(value: Any) -> list[str]:
    return [text for item in _list(value) if (text := _text(item))]


def _dict_list(value: Any) -> list[dict]:
    return [item for item in _list(value) if isinstance(item, dict)]
