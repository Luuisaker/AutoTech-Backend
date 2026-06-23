from src.core.infrastructure.mapper import GenericMapper
from src.modules.parts.domain.entity import Part, PartPurchase
from src.config.models import Part as PartModel
from src.config.models import PartPurchase as PartPurchaseModel


class PartMapper(GenericMapper[Part, PartModel]):
    def to_entity(self, model: PartModel) -> Part:
        return Part(
            id=model.id,
            workshop_id=model.workshop_id,
            name=model.name,
            description=model.description,
            price=model.price,
            stock=model.stock,
            condition=model.condition,
            category=model.category,
            allows_installments=model.allows_installments,
            installment_min_percentage=model.installment_min_percentage,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    def to_model(self, entity: Part) -> PartModel:
        return PartModel(
            id=entity.id,
            workshop_id=entity.workshop_id,
            name=entity.name,
            description=entity.description,
            price=entity.price,
            stock=entity.stock,
            condition=entity.condition,
            category=entity.category,
            allows_installments=entity.allows_installments,
            installment_min_percentage=entity.installment_min_percentage,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )


class PartPurchaseMapper(GenericMapper[PartPurchase, PartPurchaseModel]):
    def to_entity(self, model: PartPurchaseModel) -> PartPurchase:
        return PartPurchase(
            id=model.id,
            part_id=model.part_id,
            user_id=model.user_id,
            workshop_id=model.workshop_id,
            vehicle_id=model.vehicle_id,
            mileage=model.mileage,
            quantity=model.quantity,
            unit_price=model.unit_price,
            total_amount=model.total_amount,
            down_payment=model.down_payment,
            financed_amount=model.financed_amount,
            installment_count=model.installment_count,
            status=model.status,
            created_at=model.created_at,
        )

    def to_model(self, entity: PartPurchase) -> PartPurchaseModel:
        return PartPurchaseModel(
            id=entity.id,
            part_id=entity.part_id,
            user_id=entity.user_id,
            workshop_id=entity.workshop_id,
            vehicle_id=entity.vehicle_id,
            mileage=entity.mileage,
            quantity=entity.quantity,
            unit_price=entity.unit_price,
            total_amount=entity.total_amount,
            down_payment=entity.down_payment,
            financed_amount=entity.financed_amount,
            installment_count=entity.installment_count,
            status=entity.status,
            created_at=entity.created_at,
        )
