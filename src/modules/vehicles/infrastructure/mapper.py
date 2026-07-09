from src.core.infrastructure.mapper import GenericMapper
from src.modules.vehicles.domain.entity import Vehicle
from src.config.models import Vehicle as VehicleModel


class VehicleMapper(GenericMapper[Vehicle, VehicleModel]):
    def to_entity(self, model: VehicleModel) -> Vehicle:
        return Vehicle(
            id=model.id,
            owner_id=model.owner_id,
            vehicle_type=model.vehicle_type,
            brand=model.brand,
            model=model.model,
            year=model.year,
            license_plate=model.license_plate,
            vin=model.vin,
            photo_url=model.photo_url,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    def to_model(self, entity: Vehicle) -> VehicleModel:
        return VehicleModel(
            id=entity.id,
            owner_id=entity.owner_id,
            vehicle_type=entity.vehicle_type,
            brand=entity.brand,
            model=entity.model,
            year=entity.year,
            license_plate=entity.license_plate,
            vin=entity.vin,
            photo_url=entity.photo_url,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )
