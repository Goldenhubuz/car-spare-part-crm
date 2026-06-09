from decimal import Decimal
from typing import List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from starlette import status

from apps.currency.models import Currency
from apps.customer.models import Customer
from apps.document.models import Document, DocumentItemBalance, DocumentItem
from apps.notes.models import Note
from apps.product_manager.models import Item
from apps.product_manager.schemes import BuyDocumentModelScheme, SellDocumentModelScheme
from apps.purchase.models import Purchase
from di.db import db_dependency
from di.user import user_dependency
from utils.response_type import *
from .service.create_document import create_document
from .service.document_item_service import DocumentItemService
from apps.document.schemas import DocumentRead

router = APIRouter(
    prefix="/documents",
    tags=["Documents Management"],
)


@router.get("/", )
async def get_documents(
        db: db_dependency,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(10, ge=1, le=100, description="Items per page"),
):
    try:
        # 1. Optimized Query with proper eager loading
        query = (
            select(Document)
            .filter(Document.deleted_at == None)
            .order_by(desc(Document.created_at))
            .options(
                selectinload(Document.document_items)
                .selectinload(DocumentItem.item)
                .options(
                    selectinload(Item.unit),
                    selectinload(Item.category),
                    selectinload(Item.types),
                )
            )
        )

        result = await db.execute(query)
        documents = result.scalars().all()

        # 2. Map Database Models to your Response Schema
        response_data = []
        for doc in documents:
            total_qty = 0.0
            total_price_uzs = 0.0

            for item in doc.document_items:
                # Calculate Quantity
                total_qty += float(item.qty)

                # Calculate Price (Logic moved from Serializer)
                item_price = float(item.sale_price)
                qty = float(item.qty)

                if item.item.currency_type.lower() == 'usd':
                    # Use the rate stored at the time of the transaction
                    rate = float(item.currency_rate_value or 1)
                    total_price_uzs += (item_price * rate * qty)
                else:
                    total_price_uzs += (item_price * qty)

            # Create the dictionary/object for DocumentRead
            doc_data = {
                "id": doc.id,
                "doc_type": doc.doc_type,
                "created_at": doc.created_at,
                "discount": doc.discount,
                "type_of_items": len(doc.document_items),
                "count_of_items": total_qty,
                "price": total_price_uzs
            }
            response_data.append(doc_data)

        return response_data

    except Exception as e:
        # Proper error handling (Avoid 200 OK for errors)
        raise HTTPException(status_code=500, detail=str(e))


#
# @router.get("/", response_model=List[DocumentRead])
# async def get_documents(
#         db: db_dependency,
#         page: int = Query(1, ge=1, description="Page number"),
#         page_size: int = Query(10, ge=1, le=100, description="Items per page"),
# ):
#     try:
#         query = select(Document).order_by(desc('created_at')).filter_by(deleted_at=None).options(
#             selectinload(Document.document_items).selectinload(DocumentItem.item).options(
#                 selectinload(Item.unit),
#                 selectinload(Item.category),
#                 selectinload(Item.types),
#             )
#             # nested load
#         )
#         result = await db.execute(query)
#         documents = result.scalars().all()
#
#         # pagination_with_data = await  Pagination.get_paginated_data(
#         #     db, Document, DocumentSerializer, query, page, page_size
#         # )
#         return documents
#
#         # return pagination_with_data
#     except Exception as e:
#         print(e)
#         return {
#             "detail": str(e)
#         }


@router.post('/buy', status_code=status.HTTP_201_CREATED)
async def buy_document(db: db_dependency, user: user_dependency, document_scheme: BuyDocumentModelScheme):
    try:
        async with db.begin():
            # Get latest currency
            result = await db.execute(select(Currency).order_by(Currency.created_at.desc()))
            latest_currency = result.scalars().first()

            # Create document
            document = create_document(user_id=user.get("id"))
            db.add(document)
            await db.flush()
            await db.refresh(document)

            for item_scheme in document_scheme.products:
                result = await db.execute(select(Item).where(Item.id == item_scheme.item_id))
                product = result.scalar_one_or_none()
                if not product:
                    raise HTTPException(status_code=404, detail="Product not found")

                new_doc_item = DocumentItemService.create(
                    income_price=product.income_price,
                    sale_price=product.sale_price,
                    item_id=product.id,
                    item_type=item_scheme.item_type,
                    qty=Decimal(item_scheme.qty),
                    currency=latest_currency if "usd" in product.currency_type.lower() else None,
                    user_id=user.get("id"),
                    sale_percentage=Decimal("0.0"),
                    document_id=document.id,
                )
                db.add(new_doc_item)
                await db.flush()
                await db.refresh(new_doc_item)

                result = await db.execute(select(Note).where(Note.item_id == item_scheme.item_id))
                note = result.scalar_one_or_none()
                if note:
                    await note.hard_delete(db)

                result = await db.execute(
                    select(DocumentItemBalance).where(
                        DocumentItemBalance.item_id == item_scheme.item_id,
                        DocumentItemBalance.item_type == item_scheme.item_type,
                    )
                )
                item_balance = result.scalar_one_or_none()

                is_product_matched = (
                        not item_balance
                        or item_balance.income_price != new_doc_item.income_price
                        or item_balance.sale_price != new_doc_item.sale_price
                )

                if is_product_matched:
                    new_balance = DocumentItemService.create_balance(
                        user_id=user.get("id"), doc_item=new_doc_item
                    )
                    db.add(new_balance)
                    await db.flush()
                    await db.refresh(new_balance)
                else:
                    item_balance.qty += new_doc_item.qty
                    item_balance.document_item_id = new_doc_item.id
                    db.add(item_balance)
                    await db.flush()
                    await db.refresh(item_balance)

        await db.commit()
        return res_message(ResponseMessages.SUCCESS)

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/sell', status_code=status.HTTP_201_CREATED)
async def sell_document(db: db_dependency, user: user_dependency, document_scheme: SellDocumentModelScheme):
    try:

        result = await db.execute(select(Currency).order_by(Currency.created_at.desc()))
        latest_currency = result.scalars().first()

        new_document = create_document(
            user_id=user.get("id"), is_sell=True, discount=document_scheme.discount
        )
        print(f'[+] New document: {new_document}')
        db.add(new_document)
        await db.flush()
        await db.refresh(new_document)
        #
        # # Find customer
        result = await db.execute(select(Customer).where(Customer.id == document_scheme.customer_id))
        customer = result.scalar_one_or_none()

        if customer:
            purchase = Purchase(
                user_id=user.get("id"),
                customer_id=customer.id,
                document_id=new_document.id,
                remain_money=document_scheme.remain_money,
                is_debt=document_scheme.is_debt,

            )
            db.add(purchase)
            await db.flush()
            await db.refresh(purchase)

        for item_data in document_scheme.sold_products:
            result = await db.execute(
                select(DocumentItemBalance)
                .where(
                    DocumentItemBalance.item_id == item_data.item_id,
                    DocumentItemBalance.item_type == item_data.item_type,
                ).options(
                    selectinload(DocumentItemBalance.currency),
                    selectinload(DocumentItemBalance.item)
                )
                .order_by(DocumentItemBalance.created_at.asc())
            )
            product = result.scalar_one_or_none()

            if not product:
                raise HTTPException(status_code=404, detail="Balance not found")

            new_doc_item = DocumentItemService.create(
                income_price=product.income_price,
                sale_price=product.sale_price,
                item_id=product.item_id,
                item_type=item_data.item_type,
                qty=item_data.qty,
                currency=latest_currency if "usd" in product.item.currency_type.lower() else None,
                user_id=user.get("id"),
                sale_percentage=0.0,
                document_id=new_document.id,
            )
            db.add(new_doc_item)
            await db.flush()

            result = await db.execute(
                select(DocumentItemBalance).where(
                    DocumentItemBalance.item_id == item_data.item_id,
                    DocumentItemBalance.item_type == item_data.item_type,
                ).options(
                    selectinload(DocumentItemBalance.currency),
                    selectinload(DocumentItemBalance.item)
                )
            )
            item_balance = result.scalar_one_or_none()

            if item_balance:
                total_qty = item_balance.qty - item_data.qty
                item_balance.qty = total_qty
                db.add(item_balance)
                await db.flush()
                await db.refresh(item_balance)

                if total_qty == 0:
                    result = await db.execute(select(Note).where(Note.item_id == item_data.item_id))
                    note = result.scalar_one_or_none()
                    if not note:
                        note = Note(item_id=item_data.item_id)
                        db.add(note)
                        await db.flush()
                    await item_balance.hard_delete(db)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ResponseMessages.DATA_NOT_FOUND,
                )
        await db.commit()

        return res_message(ResponseMessages.SUCCESS)
    except HTTPException as e:
        await db.rollback()
        print(e)
        raise
    except Exception as e:
        print(e)
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete('/delete/{doc_id}', status_code=status.HTTP_200_OK)
async def delete_document(db: db_dependency, user: user_dependency, doc_id: int):
    try:
        async with db.begin():
            result = await db.execute(select(Document).where(Document.id == doc_id))
            document = result.scalar_one_or_none()
            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ResponseMessages.DATA_NOT_FOUND,
                )
            await document.soft_delete()
        await db.commit()
        return res_message(ResponseMessages.SUCCESS)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
