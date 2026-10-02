from sqlalchemy.orm import Session

from app.repositories.publication_repo import PublicationRepository
from app.schemas.publication import PublishPackageInput, PublishPackageResult


class PublishPackageService:
    """从用户明确选择的不可变 Draft Version 生成人工发布包。"""

    def __init__(self, db: Session, repository: PublicationRepository | None = None):
        """初始化人工发布包服务。"""
        self.repo = repository or PublicationRepository(db)

    def create_package(self, data: PublishPackageInput) -> PublishPackageResult:
        """冻结选中版本的内容，不读取 Draft root 的 latest 内容。"""
        if not self.repo.get_account(data.account_id):
            raise ValueError("账号配置不存在")
        version = self.repo.get_draft_version(data.draft_version_id)
        if not version:
            raise ValueError("Draft Version 不存在")
        draft = self.repo.get_draft(version.draft_id)
        if not draft or draft.account_id != data.account_id:
            raise ValueError("Draft Version 不存在或不属于当前账号")
        package = self.repo.create_package(data.account_id, draft, version, data.optional_publish_notes)
        return PublishPackageResult(
            package_ref=package.id, draft_id=package.draft_id,
            draft_version_id=package.draft_version_id, version_number=package.version_number,
            title=package.title, body=package.body, suggested_tags=package.tags,
            optional_publish_notes=data.optional_publish_notes,
            generated_at=getattr(package, "created_at", None),
        )
