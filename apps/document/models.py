from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from apps.base.models import Base, BaseDocumentItem
from sqlalchemy import (
    Column, Integer, String,
    ForeignKey, Numeric,
)


class Document(Base):
    __tablename__ = 'documents'
    SELL = 'sell'
    BUY = 'buy'
    doc_type = Column(String(length=4), nullable=False)
    discount = Column(Numeric(15, 3), default=0.0, nullable=True)
    # relationships
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    user = relationship('User', back_populates='documents')

    # back_populates
    document_items = relationship(
        'DocumentItem',
        back_populates='document',
        cascade='all, delete-orphan'
    )

    document_item_balances = relationship(
        'DocumentItemBalance',
        back_populates='document',
        cascade='all, delete-orphan'
    )
    purchase = relationship(
        'Purchase', back_populates='document', uselist=False)


class DocumentItem(BaseDocumentItem):
    __tablename__ = 'document_items'

    # relationships
    # user
    user = relationship('User', back_populates='document_items')
    # doc
    document = relationship('Document', back_populates='document_items')
    # currency
    currency = relationship('Currency', back_populates='document_items')
    # item
    item = relationship('Item', back_populates='document_items')

    document_item_balances = relationship(
        'DocumentItemBalance', back_populates='document_item')

    def __str__(self):
        return f"ID: {self.id} | Qty: {str(self.qty)}"

    @hybrid_property
    def total_cost(self):
        if self.item.currency_type in 'usd':
            return self.qty * self.income_price * self.currency_rate_value
        else:
            return self.qty * self.income_price


class DocumentItemBalance(BaseDocumentItem):
    __tablename__ = 'document_item_balances'

    # relationships
    # user
    user = relationship('User', back_populates='document_item_balances')
    # doc
    document = relationship(
        'Document', back_populates='document_item_balances')

    # currency
    currency = relationship(
        'Currency', back_populates='document_item_balances')
    # item
    item = relationship('Item', back_populates='document_item_balances')
    # doc_item
    document_item_id = Column(
        Integer, ForeignKey(
            'document_items.id',
        ), nullable=False,
    )

    document_item = relationship(
        'DocumentItem', back_populates='document_item_balances',
    )

    def __str__(self):
        return f"ID: {self.id} | Qty: {str(self.qty)}"
