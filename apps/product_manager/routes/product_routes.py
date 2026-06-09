from sqlalchemy import func
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select, delete, insert
from sqlalchemy.orm import selectinload

from apps.product_manager.models import Item, Type, TypeItem, Car, Category, SubCategory
from apps.company.models import Company
from apps.product_manager.schemas.product import ProductRead
from apps.product_manager.schemes import ItemCreateScheme, ItemUpdateScheme
from di.db import db_dependency
from di.user import user_dependency
from utils.pagination import pagination, PostPagination

router = APIRouter(prefix="/items", tags=["Item Management"])


# Using your generic wrapper
@router.get("/", response_model=List[Dict])
async def get_items(
        db: db_dependency,
):
    try:
        # 1. Base Query with Eager Loading
        base_query = (
            select(Item)
            .where(Item.is_deleted == False)
            .options(
                # KEEP THESE (Relationships)
                selectinload(Item.category),
                selectinload(Item.company),
                selectinload(Item.sub_category),
                selectinload(Item.unit),
                selectinload(Item.car),
                selectinload(Item.types),
            )
            .order_by(Item.created_at.desc())
        )

        result = await db.execute(base_query)
        items = result.scalars().all()
        flattened_list = []
        for item in items:
            # 1. Create the base data once per item
            base_product = {
                "id": item.id,
                "name": item.name,
                "car": item.car.name if item.car else None,
                "barcode": item.barcode,
                "company": item.company.name if item.company else None,
                "category": item.category.name if item.category else None,
                "sub_category": item.sub_category.name if item.sub_category else None,
                "income_price": item.income_price,
                "sale_price": item.sale_price,
                "unit": item.unit.value if item.unit else None,
                "currency_type": item.currency_type,
                "created_at": item.created_at if item.created_at else None,
                "updated_at": item.updated_at if item.updated_at else None,
            }

            if item.types:
                for tp in item.types:
                    row = base_product.copy()
                    row["item_type"] = tp.name
                    flattened_list.append(row)
            else:

                row = base_product.copy()
                row["item_type"] = None
                flattened_list.append(row)

        # 4. Return in your PostPagination format
        return flattened_list

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail=f"Failed to fetch items: {str(e)}")


@router.post("/add", status_code=status.HTTP_201_CREATED)
async def add_item(db: db_dependency, user: user_dependency, product_create: ItemCreateScheme):
    try:
        car = await db.get(Car, product_create.car_id) if product_create.car_id else None
        category = await db.get(Category, product_create.category_id)
        sub_category = await db.get(SubCategory,
                                    product_create.sub_category_id) if product_create.sub_category_id else None
        company = await db.get(Company, product_create.company_id) if product_create.company_id else None

        type_name = None
        if product_create.type_ids:
            types_select_query = select(Type).where(Type.id.in_(product_create.type_ids))
            type_res = await db.execute(types_select_query)
            types = type_res.scalars().all()
            if types:
                type_name = types[0].name

        name = product_create.name or Item.generate_name(
            category_name=category.name if category else None,
            sub_category_name=sub_category.name if sub_category else None,
            company_name=company.name if company else None,
        )

        barcode = product_create.barcode or Item.generate_barcode(
            category_name=category.name if category else None,
            sub_category_name=sub_category.name if sub_category else None,
            car_name=car.name if car else None,
            type_name=type_name,
            company_name=company.name if company else None,
        )

        query = select(Item).where(Item.barcode == barcode)
        res = await db.execute(query)
        product = res.scalar_one_or_none()
        if product:
            raise HTTPException(
                status_code=400, detail="Product already exists with this barcode")

        product = Item(
            name=name,
            car_id=product_create.car_id,
            barcode=barcode,
            category_id=product_create.category_id,
            sub_category_id=product_create.sub_category_id,
            income_price=product_create.income_price,
            sale_price=product_create.sale_price,
            unit_id=product_create.unit_id,
            currency_type=product_create.currency_type,
            company_id=product_create.company_id,
            user_id=user.get("id")
        )
        db.add(product)
        await db.flush()
        if product_create.type_ids:
            for i in types:
                type_item = TypeItem(
                    type_id=i.id,
                    item_id=product.id
                )
                db.add(type_item)

        await db.commit()

        return {
            "product_id": product.id,
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


@router.patch("/update/{item_id}", response_model=ProductRead)
async def update_item(db: db_dependency, user: user_dependency, item_id: int, item_body: ItemUpdateScheme):
    try:
        res = await db.execute(select(Item).where(Item.id == item_id))
        item: Item = res.scalar_one_or_none()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        item.name = item_body.name
        item.car_id = item_body.car_id
        item.barcode = item_body.barcode
        item.category_id = item_body.category_id
        item.sub_category_id = item_body.sub_category_id
        item.income_price = item_body.income_price
        item.sale_price = item_body.sale_price
        item.unit_id = item_body.unit_id
        item.currency_type = item_body.currency_type

        res = await db.execute(select(Type).where(Type.id.in_(item_body.type_ids)))
        types = res.scalars().all()

        # delete old relations
        await db.execute(
            delete(TypeItem).where(TypeItem.item_id == item.id)
        )

        # insert new
        for t in types:
            await db.execute(
                insert(TypeItem).values(item_id=item.id, type_id=t.id)
            )

        await db.commit()
        await db.refresh(item)
        final_query = await db.execute(
            select(Item).options(
                selectinload(Item.category),
                selectinload(Item.sub_category),
                selectinload(Item.unit),
                selectinload(Item.company),
                selectinload(Item.types)
            ).where(Item.id == item.id)
        )

        item = final_query.scalar_one()
        return item

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/delete/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(db: db_dependency, user: user_dependency, item_id: int):
    try:
        async with db.begin():
            res = await db.execute(select(Item).where(Item.id == item_id))
            item = res.scalar_one_or_none()
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")

            # if item_body.type_name:
            #     res = await db.execute(select(Type).where(Type.name == item_body.type_name))
            #     type_ = res.scalar_one_or_none()
            #     if not type_:
            #         raise HTTPException(status_code=404, detail="Type not found")
            #
            #     await db.execute(
            #         delete(type_item_table).where(
            #             type_item_table.c.item_id == item.id,
            #             type_item_table.c.type_id == type_.id
            #         )
            #     )
            #
            #     if len(item.types) == 0:
            #         item.soft_delete()
            # else:
            item.soft_delete()

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")
