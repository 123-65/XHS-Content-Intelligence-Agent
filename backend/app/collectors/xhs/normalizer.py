from datetime import datetime
from typing import Any

from app.collectors.xhs.base import XhsCollectedAccount, XhsCollectedComment, XhsCollectedNote


def normalize_note_payload(payload: dict[str, Any], *, source_url: str, provider_name: str, source_type: str) -> XhsCollectedNote:
    data = _unwrap(payload, "note")
    comments = [
        normalize_comment_payload(item, note_url=_text(data.get("note_url") or data.get("source_url") or source_url))
        for item in data.get("comments") or data.get("top_comments") or []
        if isinstance(item, dict)
    ]
    return XhsCollectedNote(
        note_url=_text(data.get("note_url") or data.get("source_url") or source_url),
        source_url=_text(data.get("source_url") or data.get("note_url") or source_url),
        source_type=_text(data.get("source_type")) or source_type,
        source_provider=_text(data.get("source_provider")) or provider_name,
        provider_name=_text(data.get("provider_name")) or _text(data.get("source_provider")) or provider_name,
        status=_text(data.get("status")) or "SUCCESS",
        note_id=_text(data.get("note_id") or data.get("id")),
        author_id=_text(data.get("author_id") or data.get("user_id") or data.get("userId")),
        title=_text(data.get("title")),
        content=_text(data.get("content") or data.get("desc") or data.get("description")),
        content_summary=_text(data.get("content_summary") or data.get("summary")),
        author_name=_text(data.get("author_name") or data.get("nickname") or data.get("author")),
        author_profile_url=_text(data.get("author_profile_url") or data.get("author_homepage") or data.get("profile_url")),
        publish_time=_datetime(data.get("publish_time") or data.get("created_at")),
        like_count=_int(data.get("like_count") or data.get("liked_count") or data.get("likes")),
        collect_count=_int(data.get("collect_count") or data.get("collected_count") or data.get("collects")),
        comment_count=_int(data.get("comment_count") or data.get("comments_count")),
        share_count=_int(data.get("share_count") or data.get("shares")),
        cover_url=_text(data.get("cover_url")),
        image_urls=_string_list(data.get("image_urls") or data.get("images")),
        image_ocr_texts=_string_list(data.get("image_ocr_texts") or data.get("ocr_texts")),
        card_structure=_dict_list(data.get("card_structure")),
        tags=_string_list(data.get("tags")),
        comments=comments,
        raw_payload=data.get("raw_payload") if isinstance(data.get("raw_payload"), dict) else data,
        raw_snapshot=data.get("raw_snapshot") if isinstance(data.get("raw_snapshot"), dict) else data,
        warnings=[str(item) for item in data.get("warnings") or []],
    )


def normalize_account_payload(payload: dict[str, Any], *, source_url: str, provider_name: str, source_type: str) -> XhsCollectedAccount:
    data = _unwrap(payload, "account")
    recent_notes = [
        normalize_note_payload(item, source_url=_text(item.get("note_url") or item.get("source_url") or ""), provider_name=provider_name, source_type=source_type)
        for item in data.get("recent_notes") or data.get("notes") or []
        if isinstance(item, dict)
    ]
    return XhsCollectedAccount(
        account_id=_text(data.get("account_id") or data.get("platform_account_id") or data.get("user_id") or data.get("id")),
        external_user_id=_text(data.get("external_user_id") or data.get("account_id") or data.get("platform_account_id") or data.get("user_id") or data.get("id")),
        profile_url=_text(data.get("profile_url") or data.get("homepage_url") or source_url),
        nickname=_text(data.get("nickname") or data.get("name") or data.get("user_name")),
        avatar_url=_text(data.get("avatar_url") or data.get("avatar")),
        bio=_text(data.get("bio") or data.get("description")),
        follower_count=_int(data.get("follower_count") or data.get("followers")),
        following_count=_int(data.get("following_count") or data.get("following")),
        liked_count=_int(data.get("liked_count") or data.get("likes_received")),
        recent_notes=recent_notes,
        raw_payload=data.get("raw_payload") if isinstance(data.get("raw_payload"), dict) else data,
        source_provider=_text(data.get("source_provider")) or provider_name,
        provider_name=_text(data.get("provider_name")) or _text(data.get("source_provider")) or provider_name,
        source_type=_text(data.get("source_type")) or source_type,
        status=_text(data.get("status")) or "SUCCESS",
        warnings=[str(item) for item in data.get("warnings") or []],
    )


def normalize_comment_payload(payload: dict[str, Any], *, note_url: str | None = None) -> XhsCollectedComment:
    return XhsCollectedComment(
        comment_id=_text(payload.get("comment_id") or payload.get("id")),
        note_id=_text(payload.get("note_id")),
        note_url=_text(payload.get("note_url")) or note_url,
        author_id=_text(payload.get("author_id") or payload.get("user_id") or payload.get("userId")),
        author_name=_text(payload.get("author_name") or payload.get("nickname") or payload.get("user_name")),
        content=_text(payload.get("content") or payload.get("text")) or "",
        like_count=_int(payload.get("like_count") or payload.get("likes")),
        created_at=_datetime(payload.get("created_at") or payload.get("publish_time")),
        raw_snapshot=payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else payload,
    )


def _unwrap(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else payload


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    if isinstance(value, str):
        digits = "".join(ch for ch in value.replace(",", "") if ch.isdigit())
        return int(digits) if digits else None
    return None


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _dict_list(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
