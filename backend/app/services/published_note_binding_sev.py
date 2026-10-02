from sqlalchemy.orm import Session

from app.repositories.publication_repo import PublicationRepository
from app.schemas.publication import PublishedNoteBindingInput, PublishedNoteResult


class PublishedNoteBindingService:
    """登记用户已完成的人工发布，并继承发布包的版本 lineage。"""

    def __init__(self, db: Session, repository: PublicationRepository | None = None, **_):
        """初始化不调用外部发布或采集 Provider 的登记服务。"""
        self.repo = repository or PublicationRepository(db)

    def bind(self, data: PublishedNoteBindingInput) -> PublishedNoteResult:
        """基于发布包登记，不允许再次选择或推导 Draft Version。"""
        package = self.repo.get_package(data.publish_package_ref)
        if not package or package.account_id != data.account_id:
            raise ValueError("Publish Package 不存在或不属于当前账号")
        if package.draft_version_id is None or package.version_number is None:
            raise ValueError("Publish Package 缺少 canonical Draft Version")
        draft = self.repo.get_draft(package.draft_id)
        if not draft:
            raise ValueError("Publish Package 对应的 Draft 不存在")
        note = self.repo.create_published_note(package, draft, data.publish_url, data.published_at)
        return PublishedNoteResult(
            published_note_ref=note.id, draft_id=note.draft_id,
            draft_version_id=note.draft_version_id, version_number=package.version_number,
            publish_url=note.publish_url,
            platform_note_id=(note.raw_snapshot or {}).get("platform_note_id"),
            published_at=note.published_at, bound_at=getattr(note, "created_at", None),
            account_ref=note.account_id,
        )
