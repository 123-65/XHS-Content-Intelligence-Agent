from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.models.agent_turn import AgentTurn


class AgentTurnRepository:
    def __init__(self, db): self.db = db

    def get_by_request(self, account_id, client_request_id):
        return self.db.query(AgentTurn).filter(AgentTurn.account_id == account_id, AgentTurn.client_request_id == client_request_id).one_or_none()

    def reserve(self, **fields):
        item = AgentTurn(**fields, status="PROCESSING")
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return None
        self.db.refresh(item)
        return item

    def complete(self, item, result_payload):
        item.status, item.result_payload = "COMPLETED", result_payload
        item.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit(); self.db.refresh(item)
        return item

    def fail(self, item, message):
        item.status, item.error_message = "FAILED", message[:1000]
        item.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
