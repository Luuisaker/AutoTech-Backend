from src.core.infrastructure.mapper import GenericMapper
from src.modules.cart.domain.entity import Cart, CartItem
from src.config.models import Cart as CartModel
from src.config.models import CartItem as CartItemModel


class CartMapper(GenericMapper[Cart, CartModel]):
    def to_entity(self, model: CartModel) -> Cart:
        return Cart(id=model.id, user_id=model.user_id, created_at=model.created_at)

    def to_model(self, entity: Cart) -> CartModel:
        return CartModel(id=entity.id, user_id=entity.user_id)


class CartItemMapper(GenericMapper[CartItem, CartItemModel]):
    def to_entity(self, model: CartItemModel) -> CartItem:
        return CartItem(
            id=model.id,
            cart_id=model.cart_id,
            part_id=model.part_id,
            quantity=model.quantity,
            created_at=model.created_at,
        )

    def to_model(self, entity: CartItem) -> CartItemModel:
        return CartItemModel(
            id=entity.id,
            cart_id=entity.cart_id,
            part_id=entity.part_id,
            quantity=entity.quantity,
        )
