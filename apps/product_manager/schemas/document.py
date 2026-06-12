from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional
from decimal import Decimal

from apps.product_manager.schemas.product import ProductRead


class StoreProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item: ProductRead
    item_type: str | None
    qty: float
    income_price: float
    sale_price: float
    currency_type: str


class StoreCompanyGroupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    name: str
    products: List[StoreProductRead]


class StoreCategoryGroupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    companies: List[StoreCompanyGroupSchema]
