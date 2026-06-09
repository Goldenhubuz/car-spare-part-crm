from apps import DocumentItem, DocumentItemBalance
from apps.currency.models import Currency
from apps.product_manager.models import Item


class DocumentItemService:

    @staticmethod
    def create_by_item(
            item: Item, currency: Currency, qty, sale_percentage, document_id, user_id,
    ) -> DocumentItem:
        doc_item = DocumentItem(
            document_id=document_id,
            qty=qty,
            currency_id=currency.id if currency is not None else None,
            currency_rate_value=currency.value if currency is not None else 0.0,
            income_price=item.income_price,
            sale_price=item.sale_price,
            sale_percentage=sale_percentage,
            item_id=item.id,
            user_id=user_id,
        )
        return doc_item

    @staticmethod
    def create(
            income_price, sale_price, currency: Currency, qty, sale_percentage, document_id, user_id, item_id, item_type
    ) -> DocumentItem:
        doc_item = DocumentItem(
            document_id=document_id,
            item_type=item_type,
            qty=qty,
            currency_id=currency.id if currency is not None else None,
            currency_rate_value=currency.value if currency is not None else 0.0,
            income_price=income_price,
            sale_price=sale_price,
            sale_percentage=sale_percentage,
            item_id=item_id,
            user_id=user_id,
        )
        return doc_item

    @staticmethod
    def create_balance(user_id: int, doc_item: DocumentItem) -> DocumentItemBalance:
        item_balance = DocumentItemBalance(
            item_id=doc_item.item_id,
            item_type=doc_item.item_type,
            qty=doc_item.qty,
            income_price=doc_item.income_price,
            sale_price=doc_item.sale_price,
            sale_percentage=doc_item.sale_percentage,
            user_id=user_id,
            currency_id=doc_item.currency.id if doc_item.currency is not None else None,
            currency_rate_value=doc_item.currency.value if doc_item.currency is not None else None,
            document_id=doc_item.document_id,
            document_item_id=doc_item.id,
        )
        return item_balance
