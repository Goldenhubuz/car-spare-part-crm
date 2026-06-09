from pydantic import BaseModel, Field, computed_field
from typing import List, Optional
from datetime import datetime

from apps.base.schemas import BaseModelSchema
from apps.document.schemas import DocumentRead


class PurchaseItemRead(BaseModel):
    name: str
    barcode: str
    item_type: str
    income_price: float
    sale_price: float
    qty: float
    unit: str


class PurchaseRead(BaseModelSchema):
    customer_id: int
    is_debt: bool
    paid_date: Optional[datetime]
    document: Optional[DocumentRead] = None
    total_price: float
    remain_money: float

    model_config = {
        "from_attributes": True  # This replaces class Config: from_attributes = True
    }
