from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List

from apps.base.schemas import BaseModelSchema


class TypeRead(BaseModelSchema):
    name: str

    class Config:
        from_attributes = True


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    car: str
    barcode: str
    category: str
    sub_category: str | None = None
    income_price: float
    sale_price: float
    unit: str
    currency_type: str
    item_type: str | None = None

    # 1. Fix the Unit object -> string error
    @field_validator('unit', mode='before')
    @classmethod
    def transform_unit(cls, v):
        if hasattr(v, 'value'):  # If it's the Unit object, get the .value
            return v.value
        return str(v)

    # 2. Fix the Category object -> string error
    @field_validator('category', mode='before')
    @classmethod
    def transform_category(cls, v):
        if hasattr(v, 'name'):  # If it's the Category object, get the .name
            return v.name
        return str(v)

    @field_validator('sub_category', mode='before')
    @classmethod
    def transform_sub_category(cls, v):
        if hasattr(v, 'name'):
            return v.name
        return str(v) if v else None

    # 3. Fix the Car object -> string error
    @field_validator('car', mode='before')
    @classmethod
    def transform_car_rel(cls, v):
        if hasattr(v, 'name'):  # If it's the Car object, get the .name
            return v.name
        return str(v)

    @field_validator('item_type', mode='before')
    @classmethod
    def transform_item_type(cls, v):
        if hasattr(v, 'name'):  # If it's a Type object, get the .name
            return v.name
        return str(v) if v else None


class ProductCreatedRes(BaseModel):
    id: int
    name: str
    barcode: str
    category: str
    income_price: float
    sale_price: float
    unit: str
    currency_type: str

    # Fixed: Match the Pydantic field name to your logic or the DB attribute

    # 1. Fix the Unit object -> string error
    @field_validator('unit', mode='before')
    @classmethod
    def transform_unit(cls, v):
        if hasattr(v, 'value'):  # If it's the Unit object, get the .value
            return v.value
        return str(v)

    # 2. Fix the Category object -> string error
    @field_validator('category', mode='before')
    @classmethod
    def transform_category(cls, v):
        if hasattr(v, 'name'):  # If it's the Category object, get the .name
            return v.name
        return str(v)


class CompanyGroupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    name: str
    products: List[ProductRead]


class CategoryGroupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    name: str
    companies: List[CompanyGroupSchema]
