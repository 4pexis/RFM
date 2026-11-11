from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.events import EventBus
from app.core.security import AccessControl
from app.database.connection import Database
from app.database.models import ActivityLog


class BaseManager:
    """Base das regras de negócio: banco, eventos, permissões e auditoria."""

    def __init__(self, db: Database, events: EventBus, access: AccessControl) -> None:
        self.db = db
        self.events = events
        self.access = access
        self.log = logging.getLogger(type(self).__module__)

    def _audit(
        self, session: Session, action: str, entity_type: str = "",
        entity_id: int | None = None, details: str = "",
    ) -> None:
        session.add(ActivityLog(
            actor=self.access.role, action=action, entity_type=entity_type,
            entity_id=entity_id, details=details[:2000],
        ))
        self.log.info(action, extra={"entity": entity_type, "entity_id": entity_id, "details": details})
