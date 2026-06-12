from typing import Any, Set, Tuple

from sqladmin import ModelView
from sqlalchemy import Select, false, or_, cast, select, String
from .models import Item, Category, SubCategory, Unit, Type, TypeItem, Car
from apps.company.models import Company
from config.database_config import async_session_factory


class ItemAdmin(ModelView, model=Item):
    column_list = [
        Item.id,
        Item.name,
        "car.name",
        "company.name",
        Item.barcode,
        "category.name",
        "sub_category.name",
        Item.income_price,
        Item.sale_price,
        Item.unit,
        Item.currency_type,
        "types",
    ]
    column_searchable_list = [Item.name, Item.barcode, "category.name", "sub_category.name", "company.name"]
    name = "Item"
    icon = "fa-solid fa-box"
    column_default_sort = [(Item.id, True)]

    @staticmethod
    def _outer_join_relationship_paths(
        stmt: Select,
        field_path: str,
        joined_paths: Set[str],
        model: type,
    ) -> Tuple[Select, Any]:
        parts = field_path.split(".")
        current_path = ""
        for part in parts[:-1]:
            current_path = f"{current_path}.{part}" if current_path else part
            relationship_attr = getattr(model, part)
            next_model = relationship_attr.mapper.class_
            if current_path not in joined_paths:
                stmt = stmt.outerjoin(relationship_attr)
                joined_paths.add(current_path)
            model = next_model
        return stmt, model

    def search_query(self, stmt: Select, term: str) -> Select:
        expressions = []
        joined_paths: Set[str] = set()

        for field in self._search_fields:
            stmt, model = self._outer_join_relationship_paths(
                stmt, field, joined_paths, self.model
            )
            parts = field.split(".")
            field_attr = getattr(model, parts[-1])
            expressions.append(cast(field_attr, String).ilike(f"%{term}%"))

        return stmt.filter(or_(false(), *expressions))

    async def _resolve_related(self, session, data, model, name):
        val = data.get(name) or data.get(
            f"{name}_id") or getattr(model, f"{name}_id", None)
        if val is None:
            return None
        models_map = {
            "category": Category, "sub_category": SubCategory,
            "car": Car, "company": Company,
        }
        try:
            pk = int(val) if not isinstance(val, int) else val
        except (ValueError, TypeError):
            return None
        return await session.get(models_map[name], pk)

    async def on_model_change(self, data, model, is_created, request):
        name = data.get("name")
        async with async_session_factory() as session:
            category = await self._resolve_related(session, data, model, "category")
            sub_category = await self._resolve_related(session, data, model, "sub_category")
            car = await self._resolve_related(session, data, model, "car")
            company = await self._resolve_related(session, data, model, "company")

            types_val = data.get("types") or getattr(model, "types", None)
            if name is None:
                new_name = Item.generate_name(
                    category_name=category.name if category else None,
                    sub_category_name=sub_category.name if sub_category else None,
                    company_name=company.name if company else None,
                )
                if name:
                    data["name"] = new_name
                    model.name = new_name

            type_name = types_val[0] if types_val else None

            barcode = Item.generate_barcode(
                category_name=category.name if category else None,
                sub_category_name=sub_category.name if sub_category else None,
                car_name=car.name if car else None,
                type_name=type_name,
                company_name=company.name if company else None,
            )

            if barcode:
                existing = await session.execute(
                    select(Item).where(Item.barcode ==
                                       barcode, Item.id != (model.id or 0))
                )
                if existing.scalar_one_or_none():
                    suffix = 1
                    while True:
                        new_barcode = f"{barcode}_{suffix}"
                        ex = await session.execute(
                            select(Item).where(Item.barcode ==
                                               new_barcode, Item.id != (model.id or 0))
                        )
                        if not ex.scalar_one_or_none():
                            barcode = new_barcode
                            break
                        suffix += 1

                data["barcode"] = barcode
                model.barcode = barcode


class CategoryAdmin(ModelView, model=Category):
    column_list = [Category.id, Category.name]
    column_searchable_list = [Category.name]
    name = "Category"
    icon = "fa-solid fa-tags"

    column_default_sort = [(Category.id, True)]


class UnitAdmin(ModelView, model=Unit):
    column_list = [Unit.id, Unit.value]
    column_searchable_list = [Unit.value]
    name = "Unit"
    icon = "fa-solid fa-balance-scale"
    column_default_sort = [(Unit.id, True)]


class TypeAdmin(ModelView, model=Type):
    column_list = [Type.id, Type.name]
    column_searchable_list = [Type.name]
    name = "Type"
    icon = "fa-solid fa-layer-group"
    column_default_sort = [(Type.id, True)]


class TypeItemAdmin(ModelView, model=TypeItem):
    column_list = [TypeItem.type_id, TypeItem.item_id]
    name = "Type Item"
    icon = "fa-solid fa-link"


class CarAdmin(ModelView, model=Car):
    column_list = [Car.id, Car.name]
    column_searchable_list = [Car.name]
    name = "Car"
    icon = "fa-solid fa-car"
    column_default_sort = [(Car.id, True)]


class SubCategoryAdmin(ModelView, model=SubCategory):
    column_list = [SubCategory.id, SubCategory.name, "category.name"]
    column_searchable_list = [SubCategory.name]
    name = "Sub Category"
    icon = "fa-solid fa-tag"
    column_default_sort = [(SubCategory.id, True)]
