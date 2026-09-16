from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.publish_package import PublishPackage
from app.schemas.publish_package import PublishPackageCreate


class PublishPackageRepository:
    """Database access for manual publish packages."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: PublishPackageCreate) -> PublishPackage:
        package = PublishPackage(**data.model_dump())
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def get_by_id(self, package_id: int) -> PublishPackage | None:
        return self.db.get(PublishPackage, package_id)

    def list_by_draft(self, draft_id: int) -> list[PublishPackage]:
        stmt = select(PublishPackage).where(PublishPackage.draft_id == draft_id).order_by(PublishPackage.id.desc())
        return list(self.db.execute(stmt).scalars().all())
