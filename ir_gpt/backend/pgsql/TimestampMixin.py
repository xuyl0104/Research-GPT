from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import Column, DateTime
from datetime import datetime, timezone

class TimestampMixin:
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
