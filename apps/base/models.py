from datetime import datetime

import pytz
from sqlalchemy import Integer, Column, DateTime, Boolean, String
from sqlalchemy import Numeric, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import as_declarative, Session

from config.settings import settings


@as_declarative()
class Base:
    __abstract__ = True
    __tablename__ = None

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_deleted = Column(Boolean, default=False, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    @staticmethod
    def tashkent_now(context=None):
        """
        Return a tz-naive datetime in Asia/Tashkent
        (compatible with TIMESTAMP WITHOUT TIME ZONE)
        """
        tz = pytz.timezone(settings.TIME_ZONE)
        return datetime.now(tz).replace(tzinfo=None)

    created_at = Column(DateTime, default=tashkent_now)
    updated_at = Column(DateTime, default=tashkent_now, onupdate=tashkent_now)

    def reset(self):
        self.is_deleted = False
        self.deleted_at = None

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = Base.tashkent_now()

    async def hard_delete(self, db: AsyncSession):
        await db.delete(self)


class BaseDocumentItem(Base):
    __abstract__ = True
    qty = Column(Numeric(25, 5), default=0, nullable=False)
    income_price = Column(Numeric(25, 5), nullable=False, default=0.0)
    sale_price = Column(Numeric(25, 5), nullable=False, default=0.0)
    sale_percentage = Column(Numeric(15, 2), nullable=False, default=0.0)
    currency_rate_value = Column(Numeric(15, 2), nullable=True)
    # relationships
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    item_type = Column(String, nullable=True)
    currency_id = Column(Integer, ForeignKey('currencies.id'), nullable=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
