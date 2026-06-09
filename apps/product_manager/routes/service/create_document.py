from apps import Document


def create_document(
        user_id, is_sell: bool = False, discount=0.0,
) -> Document:
    document = Document(
        doc_type=Document.SELL if is_sell else Document.BUY,
        user_id=user_id, discount=discount
    )
    return document
