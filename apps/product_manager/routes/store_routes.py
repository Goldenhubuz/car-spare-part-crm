from collections import defaultdict
from typing import List

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload

from apps.document.models import DocumentItemBalance
from apps.product_manager.models import Item
from apps.product_manager.schemes import DocumentItemBalanceUpdatedScheme
from di.db import db_dependency
from di.user import user_dependency
from utils.response_type import *
from .serializers.store_serializers import StoreSchemaRead
from ..schemas.document import StoreProductRead, StoreCompanyGroupSchema, StoreCategoryGroupSchema
from ..schemas.product import ProductRead

router = APIRouter(
    prefix="/store",
    tags=["Store Management"],
)


@router.get("", status_code=status.HTTP_200_OK, response_model=List[StoreSchemaRead])
async def get_products_in_store(
        db: db_dependency,
        user: user_dependency,
):
    try:
        query = (
            select(DocumentItemBalance)
            .options(
                selectinload(DocumentItemBalance.item).options(
                    selectinload(Item.unit),
                    selectinload(Item.category),
                    selectinload(Item.sub_category),
                    selectinload(Item.car),
                    selectinload(Item.document_item_balances)
                ),
                selectinload(DocumentItemBalance.currency),
                selectinload(DocumentItemBalance.document)
            )
        )
        result = await db.execute(query)
        products = result.scalars().all()

        return products
    except Exception as e:
        raise HTTPException(
            detail=str(e), status_code=status.HTTP_400_BAD_REQUEST
        )


@router.get("/groups", status_code=status.HTTP_200_OK, response_model=List[StoreCategoryGroupSchema])
async def get_groups(db: db_dependency):
    try:
        query = (
            select(DocumentItemBalance).options(
                joinedload(DocumentItemBalance.item).joinedload(Item.category),
                joinedload(DocumentItemBalance.item).joinedload(Item.sub_category),
                joinedload(DocumentItemBalance.item).joinedload(Item.car),
                joinedload(DocumentItemBalance.item).joinedload(Item.company),
                joinedload(DocumentItemBalance.item).joinedload(Item.unit),
                joinedload(DocumentItemBalance.item).joinedload(Item.types),  # 1. Load many-to-many item types
            )
        )
        result = await db.execute(query)
        balances = result.unique().scalars().all()  # <-- Added .unique() here

        hierarchical_data = defaultdict(lambda: defaultdict(list))

        for balance in balances:
            product = balance.item
            if not product or not product.category:
                continue

            category = product.category
            company = product.company

            cat_key = (category.id, category.name)
            if company:
                comp_key = (company.id, company.name)
            else:
                comp_key = (0, "No Company")

            # 2. Split item if it contains multiple types
            if product.types:
                for current_type in product.types:
                    product_payload = StoreProductRead(
                        id=product.id,
                        item=ProductRead.model_validate(product),
                        item_type=current_type.name,  # Assign individual type name
                        qty=float(balance.qty),
                        income_price=float(balance.income_price),
                        sale_price=float(balance.sale_price),
                        currency_type=product.currency_type
                    )
                    hierarchical_data[cat_key][comp_key].append(product_payload)
            else:
                # Fallback if the item has no types assigned
                product_payload = StoreProductRead(
                    id=product.id,
                    item=ProductRead.model_validate(product),
                    item_type=None,
                    qty=float(balance.qty),
                    income_price=float(balance.income_price),
                    sale_price=float(balance.sale_price),
                    currency_type=product.currency_type
                )
                hierarchical_data[cat_key][comp_key].append(product_payload)

        formatted_response = []
        for (cat_id, cat_name), companies_dict in hierarchical_data.items():
            companies_list = []
            for (comp_id, comp_name), products in companies_dict.items():
                companies_list.append(
                    StoreCompanyGroupSchema(
                        id=comp_id if comp_id != 0 else None,
                        name=comp_name,
                        products=products
                    )
                )

            formatted_response.append(
                StoreCategoryGroupSchema(
                    id=cat_id,
                    name=cat_name,
                    companies=companies_list
                )
            )
        return formatted_response

    except Exception as e:
        # Cast exception to string so HTTPException can safely serialize it
        raise HTTPException(detail=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@router.get("/fetch", response_model=List[StoreSchemaRead], status_code=status.HTTP_200_OK)
async def get_store(db: db_dependency, user: user_dependency):
    try:
        result = await db.execute(
            select(DocumentItemBalance)
            .options(
                selectinload(DocumentItemBalance.item).options(
                    selectinload(Item.unit),
                    selectinload(Item.category),
                    selectinload(Item.sub_category),
                    selectinload(Item.car),
                    selectinload(Item.document_item_balances)
                ),
                selectinload(DocumentItemBalance.currency),
                selectinload(DocumentItemBalance.document)
            )
        )
        products = result.scalars().unique().all()

        return products

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error: {str(e)}"
        )


@router.patch("/update-item-balance/{item_balance_id}", status_code=status.HTTP_200_OK)
async def update_item_balance(
        db: db_dependency,
        user: user_dependency,
        item_scheme: DocumentItemBalanceUpdatedScheme,
        item_balance_id: int
):
    try:
        async with db.begin():
            result = await db.execute(
                select(DocumentItemBalance).where(
                    DocumentItemBalance.id == item_balance_id)
            )
            item_balance = result.scalar_one_or_none()

            if not item_balance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Item balance not found"
                )

            # Update fields safely
            if item_scheme.qty is not None:
                item_balance.qty = item_scheme.qty
            if item_scheme.income_price is not None:
                item_balance.income_price = item_scheme.income_price
            if item_scheme.selling_price is not None:
                item_balance.sale_price = item_scheme.selling_price
            if item_scheme.selling_percentage is not None:
                item_balance.sale_percentage = item_scheme.selling_percentage

            await db.commit()
            await db.refresh(item_balance)

            return response_item(item_balance)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error: {str(e)}"
        )
