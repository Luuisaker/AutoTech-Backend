from src.core.infrastructure.mapper import GenericMapper
from src.modules.orders.domain.entity import Order, OrderItem
from src.config.models import (
    Order as OrderModel,
    OrderItem as OrderItemModel,
)


class OrderMapper(GenericMapper[Order, OrderModel]):
    def to_entity(self, model: OrderModel) -> Order:
        return Order(
            id=model.id,
            user_id=model.user_id,
            vehicle_id=model.vehicle_id,
            mileage=model.mileage,
            total_amount=model.total_amount,
            status=model.status,
            delivery_method=model.delivery_method,
            delivery_address=model.delivery_address,
            delivery_fee=model.delivery_fee,
            reference_number=model.reference_number,
            confirmed_at=model.confirmed_at,
            closed_by_client=bool(model.closed_by_client),
            closed_by_workshop=bool(model.closed_by_workshop),
            created_at=model.created_at,
        )

    def to_model(self, entity: Order) -> OrderModel:
        return OrderModel(
            id=entity.id,
            user_id=entity.user_id,
            vehicle_id=entity.vehicle_id,
            mileage=entity.mileage,
            total_amount=entity.total_amount,
            status=entity.status,
            delivery_method=entity.delivery_method,
            delivery_address=entity.delivery_address,
            delivery_fee=entity.delivery_fee,
            reference_number=entity.reference_number,
            confirmed_at=entity.confirmed_at,
            closed_by_client=int(entity.closed_by_client),
            closed_by_workshop=int(entity.closed_by_workshop),
        )


class OrderItemMapper(GenericMapper[OrderItem, OrderItemModel]):
    def to_entity(self, model: OrderItemModel) -> OrderItem:
        return OrderItem(
            id=model.id,
            order_id=model.order_id,
            part_id=model.part_id,
            workshop_id=model.workshop_id,
            part_name=model.part_name,
            quantity=model.quantity,
            unit_price=model.unit_price,
        )

    def to_model(self, entity: OrderItem) -> OrderItemModel:
        return OrderItemModel(
            id=entity.id,
            order_id=entity.order_id,
            part_id=entity.part_id,
            workshop_id=entity.workshop_id,
            part_name=entity.part_name,
            quantity=entity.quantity,
            unit_price=entity.unit_price,
        )
